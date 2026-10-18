"""Read-only source export contracts; no HTTP services are hosted by tests."""
import importlib.util
import json
import io
import os
import subprocess
from urllib.error import HTTPError
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parents[1] / "linear_export.py"
TEAM = "00000000-0000-0000-0000-000000000001"
ORG = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def exporter():
    spec = importlib.util.spec_from_file_location("linear_export", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def issue(number, **changes):
    return {"id": "10000000-0000-0000-0000-%012d" % number,
            "identifier": "FAS-%d" % number, "title": "Synthetic %d" % number,
            "team": {"id": TEAM}, "archivedAt": None, **changes}


class Provider:
    def __init__(self, pages):
        self.pages = list(pages)
        self.requests = []

    def __call__(self, query, variables):
        self.requests.append((query, variables))
        if "ExportScope" in query:
            return {"data": {"organization": {"id": ORG, "name": "Synthetic"},
                             "team": {"id": TEAM, "key": "FAS", "name": "Synthetic"}}}
        return self.pages.pop(0)


def page(nodes, more=False, cursor=None):
    return {"data": {"issues": {"nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": cursor}}}}


def test_export_retains_every_page_and_archived_payload(exporter, tmp_path):
    source = Provider([page([issue(2)], True, "next"), page([issue(11, archivedAt="2026-01-01T00:00:00Z")])])
    destination = tmp_path / "private-export"
    result = exporter.export_issues(source, TEAM, destination)
    assert result["issue_count"] == 2
    assert result["status"] == "COMPLETE_FOR_ISSUES"
    assert result["atomic_snapshot"] is False
    saved = [json.loads((destination / p["file"]).read_text()) for p in result["pages"]]
    assert [n["identifier"] for p in saved for n in p["data"]["issues"]["nodes"]] == ["FAS-2", "FAS-11"]
    assert saved[1]["data"]["issues"]["nodes"][0]["archivedAt"] == "2026-01-01T00:00:00Z"
    assert source.requests[1][1]["filter"] == {"team": {"id": {"eq": TEAM}}}
    assert "includeArchived: true" in source.requests[1][0]
    assert source.requests[2][1]["cursor"] == "next"


def test_export_outputs_private_files_and_will_not_overwrite(exporter, tmp_path):
    directory = tmp_path / "out"
    exporter.export_issues(Provider([page([issue(2)])]), TEAM, directory)
    before = (directory / "manifest.json").read_bytes()
    assert directory.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o077 == 0 for p in directory.iterdir())
    with pytest.raises(FileExistsError):
        exporter.export_issues(Provider([]), TEAM, directory)
    assert (directory / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("failure,code", [
    (page([issue(2), issue(2)]), "DUPLICATE_IDENTITY"),
    (page([issue(2, team={"id": ORG})]), "TEAM_BOUNDARY"),
    (page([issue(2)], True, None), "CURSOR_LOOP"),
    ({"data": {"issues": {"nodes": None, "pageInfo": {"hasNextPage": False, "endCursor": None}}}}, "SOURCE_SHAPE"),
    (page([issue(2, labels={"pageInfo": {"hasNextPage": True}})]), "NESTED_PAGINATION"),
    ({"data": {"issues": None}, "errors": [{"message": "private-provider-error-fixture"}]}, "GRAPHQL_ERROR"),
])
def test_invalid_or_partial_source_cannot_be_export_success(exporter, tmp_path, failure, code):
    directory = tmp_path / "out"
    with pytest.raises(exporter.SourceError, match=code):
        exporter.export_issues(Provider([failure]), TEAM, directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "FAILED"
    assert manifest["issue_count"] == 0
    assert "private-provider-error-fixture" not in (directory / "manifest.json").read_text()


def test_cursor_loop_after_a_committed_page_preserves_checkpoint(exporter, tmp_path):
    directory = tmp_path / "out"
    with pytest.raises(exporter.SourceError, match="CURSOR_LOOP"):
        exporter.export_issues(Provider([page([issue(2)], True, "repeat"), page([issue(5)], True, "repeat")]), TEAM, directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert len(manifest["pages"]) == 1
    assert manifest["issue_count"] == 1
    assert manifest["next_cursor"] == "repeat"


def test_auth_failure_then_resume_keeps_original_records_once(exporter, tmp_path):
    directory = tmp_path / "out"
    with pytest.raises(exporter.SourceError, match="GRAPHQL_ERROR"):
        exporter.export_issues(Provider([page([issue(2)], True, "next"), {"errors": [{"message": "reauth required"}]}]), TEAM, directory)
    first = (directory / "page-000001.json").read_bytes()
    recovered = Provider([page([issue(11)])])
    result = exporter.export_issues(recovered, TEAM, directory, resume=True)
    assert recovered.requests[1][1]["cursor"] == "next"
    assert result["issue_count"] == 2
    assert result["status"] == "COMPLETE_FOR_ISSUES"
    assert (directory / "page-000001.json").read_bytes() == first
    assert len(result["pages"]) == 2


def test_resume_detects_tampering_and_scope_changes(exporter, tmp_path):
    directory = tmp_path / "out"
    exporter.export_issues(Provider([page([issue(2)])]), TEAM, directory)
    raw = json.loads((directory / "page-000001.json").read_text())
    raw["data"]["issues"]["nodes"][0]["title"] = "Tampered fixture"
    (directory / "page-000001.json").write_text(json.dumps(raw))
    with pytest.raises(exporter.SourceError, match="CHECKSUM_MISMATCH"):
        exporter.export_issues(Provider([]), TEAM, directory, resume=True)
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["team_id"] = ORG
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(exporter.SourceError, match="RESUME_SCOPE"):
        exporter.export_issues(Provider([]), TEAM, directory, resume=True)


def test_export_rejects_git_destination_before_private_write(exporter, tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    with pytest.raises(exporter.SourceError, match="OUTPUT_IN_GIT"):
        exporter.export_issues(Provider([]), TEAM, tmp_path / "nested/private")
    assert not (tmp_path / "nested").exists()


def test_foreign_parent_is_an_explicit_stub_not_a_foreign_payload(exporter, tmp_path):
    foreign = {"id": "20000000-0000-0000-0000-000000000001", "identifier": "OTHER-1", "team": {"id": ORG}}
    result = exporter.export_issues(Provider([page([issue(2, parent=foreign)])]), TEAM, tmp_path / "out")
    assert result["boundary_references"] == [{"source_issue_id": issue(2)["id"], "entity_type": "issue", "id": foreign["id"], "identifier": "OTHER-1", "team_id": ORG}]


class HTTPProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(json.dumps(value).encode())


def test_transport_bounds_rate_retry_and_preserves_fixed_endpoint(exporter):
    provider = HTTPProvider([HTTPError("https://api.linear.app/graphql", 429, "rate", {"Retry-After": "999"}, io.BytesIO()), {"data": {"ok": True}}])
    delays = []
    result = exporter.LinearHTTP("fake-read-token", provider, delays.append)("query Example { viewer { id } }", {})
    assert result == {"data": {"ok": True}}
    assert delays == [30]
    assert len(provider.requests) == 2
    assert all(r.full_url == "https://api.linear.app/graphql" and timeout == 30 for r, timeout in provider.requests)
    assert all(r.get_header("Authorization") == "fake-read-token" for r, _ in provider.requests)
    assert "fake-read-token" not in provider.requests[0][0].data.decode()


def test_transport_never_logs_or_retries_authorization_error(exporter):
    response = HTTPError("https://api.linear.app/graphql", 401, "private-error", {}, io.BytesIO(b"private response body"))
    provider = HTTPProvider([response])
    with pytest.raises(exporter.SourceError) as failure:
        exporter.LinearHTTP("fake-read-token", provider)("query Example { viewer { id } }", {})
    assert str(failure.value) == "SOURCE_HTTP_401"
    assert len(provider.requests) == 1
    assert response.fp.closed


def test_empty_export_is_explicit_not_a_hidden_source_error(exporter, tmp_path):
    result = exporter.export_issues(Provider([page([])]), TEAM, tmp_path / "out")
    assert result["issue_count"] == 0
    assert len(result["pages"]) == 1
    assert result["status"] == "COMPLETE_FOR_ISSUES"


def test_page_limit_is_bounded_and_resume_can_continue(exporter, tmp_path):
    directory = tmp_path / "out"
    with pytest.raises(exporter.SourceError, match="PAGE_LIMIT"):
        exporter.export_issues(Provider([page([issue(2)], True, "next")]), TEAM, directory, max_pages=1)
    result = exporter.export_issues(Provider([page([issue(11)])]), TEAM, directory, resume=True, max_pages=2)
    assert result["issue_count"] == 2


def test_cancel_after_commit_preserves_recoverable_checkpoint(exporter, tmp_path):
    class Interrupted(Provider):
        def __call__(self, query, variables):
            if "ExportIssues" in query and variables["cursor"] == "next":
                raise KeyboardInterrupt()
            return super().__call__(query, variables)
    directory = tmp_path / "out"
    with pytest.raises(exporter.SourceError, match="INTERRUPTED"):
        exporter.export_issues(Interrupted([page([issue(2)], True, "next")]), TEAM, directory)
    result = exporter.export_issues(Provider([page([issue(11)])]), TEAM, directory, resume=True)
    assert result["issue_count"] == 2


def test_active_export_cannot_be_overwritten_by_second_run(exporter, tmp_path):
    import fcntl
    directory = tmp_path / "out"
    exporter.export_issues(Provider([page([issue(2)])]), TEAM, directory)
    before = (directory / "manifest.json").read_bytes()
    with (directory / ".lock").open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(exporter.SourceError, match="EXPORT_LOCKED"):
            exporter.export_issues(Provider([]), TEAM, directory, resume=True)
    assert (directory / "manifest.json").read_bytes() == before


def test_transport_exhausts_retries_and_closes_every_error(exporter):
    errors = [HTTPError("https://api.linear.app/graphql", 429, "rate", {"Retry-After": "0"}, io.BytesIO()) for _ in range(3)]
    provider, delays = HTTPProvider(errors), []
    with pytest.raises(exporter.SourceError, match="SOURCE_HTTP_429"):
        exporter.LinearHTTP("fake-read-token", provider, delays.append)("query Example { viewer { id } }", {})
    assert len(provider.requests) == 3
    assert delays == [0, 0]
    assert all(error.fp.closed for error in errors)


def test_budget_failure_does_not_write_a_partial_page(exporter, tmp_path):
    directory = tmp_path / "out"
    with pytest.raises(exporter.SourceError, match="EXPORT_BUDGET"):
        exporter.export_issues(Provider([page([issue(2)])]), TEAM, directory, max_bytes=1)
    assert list(directory.glob("page-*.json")) == []
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "FAILED"
    assert manifest["issue_count"] == 0
    recovered = exporter.export_issues(Provider([page([issue(2)])]), TEAM, directory, resume=True)
    assert recovered["issue_count"] == 1


def test_original_unicode_description_and_actor_payload_are_preserved(exporter, tmp_path):
    node = issue(2, description="Synthetic café\n👗 <script>data only</script>",
                 creator={"id": ORG, "name": "Synthetic author", "email": "fixture@example.invalid"})
    directory = tmp_path / "out"
    exporter.export_issues(Provider([page([node])]), TEAM, directory)
    saved = json.loads((directory / "page-000001.json").read_text(encoding="utf-8"))
    assert saved["data"]["issues"]["nodes"] == [node]


def test_transport_does_not_accept_a_response_after_deadline(exporter):
    provider = HTTPProvider([{"data": {"ok": True}}])
    clock = iter([0, 0, 31])
    with pytest.raises(exporter.SourceError, match="SOURCE_TIMEOUT"):
        exporter.LinearHTTP("fake-read-token", provider, clock=lambda: next(clock))("query Example { viewer { id } }", {})


@pytest.mark.parametrize('value', [None, [], {'schema_version': 99}, {'pages': None}])
def test_invalid_checkpoint_is_rejected_without_modifying_it(exporter, tmp_path, value):
    directory = tmp_path / 'out'
    exporter.export_issues(Provider([page([issue(2)])]), TEAM, directory)
    saved = directory / 'manifest.json'
    saved.write_text(json.dumps(value))
    before = saved.read_bytes()
    with pytest.raises(exporter.SourceError, match='RESUME_SHAPE'):
        exporter.export_issues(Provider([]), TEAM, directory, resume=True)
    assert saved.read_bytes() == before


def test_rejected_scope_and_checksum_leave_original_manifest_unchanged(exporter, tmp_path):
    directory = tmp_path / 'out'
    exporter.export_issues(Provider([page([issue(2)])]), TEAM, directory)
    saved = directory / 'manifest.json'
    original = saved.read_bytes()
    changed = json.loads(original)
    changed['team_id'] = ORG
    saved.write_text(json.dumps(changed))
    before = saved.read_bytes()
    with pytest.raises(exporter.SourceError, match='RESUME_SCOPE'):
        exporter.export_issues(Provider([]), TEAM, directory, resume=True)
    assert saved.read_bytes() == before
    saved.write_bytes(original)
    (directory / 'page-000001.json').write_text('tampered fixture')
    with pytest.raises(exporter.SourceError, match='CHECKSUM_MISMATCH'):
        exporter.export_issues(Provider([]), TEAM, directory, resume=True)
    assert saved.read_bytes() == original


def test_indeterminate_git_check_creates_no_output(exporter, tmp_path, monkeypatch):
    monkeypatch.setattr(exporter.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 128, b'', b'fatal: detected dubious ownership'))
    source = Provider([])
    with pytest.raises(exporter.SourceError, match='GIT_DETECTION'):
        exporter.export_issues(source, TEAM, tmp_path / 'private')
    assert source.requests == []
    assert not (tmp_path / 'private').exists()


def test_broken_git_marker_still_blocks_private_output(exporter, tmp_path):
    (tmp_path / '.git').mkdir()
    with pytest.raises(exporter.SourceError, match='OUTPUT_IN_GIT'):
        exporter.export_issues(Provider([]), TEAM, tmp_path / 'private')
    assert not (tmp_path / 'private').exists()
