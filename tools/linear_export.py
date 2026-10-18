"""Read-only Linear issue export; source coverage is expanded by later tickets."""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCOPE_QUERY = """query ExportScope($team: String!) {
  organization { id name urlKey }
  team(id: $team) { id key name }
}"""
ISSUE_QUERY = """query ExportIssues($filter: IssueFilter!, $cursor: String) {
  issues(filter: $filter, first: 50, after: $cursor,
         includeArchived: true, orderBy: createdAt) {
    nodes {
      id identifier title description priority estimate url branchName
      createdAt updatedAt archivedAt startedAt completedAt canceledAt dueDate
      state { id name type } team { id name key }
      project { id name } cycle { id number }
      parent { id identifier team { id } }
      creator { id name email } assignee { id name email }
      labels(first: 50, includeArchived: true) {
        nodes { id name } pageInfo { hasNextPage endCursor }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}"""
QUERY_HASH = hashlib.sha256((SCOPE_QUERY + ISSUE_QUERY).encode()).hexdigest()


class SourceError(Exception):
    """Safe public error code; never include raw provider error bodies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class LinearHTTP:
    def __init__(self, token, opener=None, sleep=time.sleep, clock=time.monotonic):
        if not token:
            raise SourceError("MISSING_CREDENTIAL")
        self.token = token
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep
        self.clock = clock

    def __call__(self, query, variables):
        request = Request("https://api.linear.app/graphql",
                          data=json.dumps({"query": query, "variables": variables}).encode(),
                          headers={"Authorization": self.token, "Content-Type": "application/json"})
        for attempt in range(3):
            try:
                deadline = self.clock() + 30
                with self.opener.open(request, timeout=30) as response:
                    chunks, size = [], 0
                    while size <= 16 * 1024 * 1024:
                        if self.clock() >= deadline:
                            raise SourceError("SOURCE_TIMEOUT")
                        chunk = response.read1(min(65536, 16 * 1024 * 1024 + 1 - size))
                        if self.clock() >= deadline:
                            raise SourceError("SOURCE_TIMEOUT")
                        if not chunk:
                            break
                        chunks.append(chunk)
                        size += len(chunk)
                    raw = b"".join(chunks)
                if len(raw) > 16 * 1024 * 1024:
                    raise SourceError("RESPONSE_TOO_LARGE")
                return json.loads(raw)
            except HTTPError as error:
                status, headers = error.code, error.headers or {}
                error.close()
                if status not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise SourceError("SOURCE_HTTP_" + str(status)) from None
                try:
                    delay = float(headers.get("Retry-After", 2 ** attempt))
                except (ValueError, TypeError):
                    delay = 2 ** attempt
                self.sleep(max(0, min(delay, 30)))
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise SourceError("SOURCE_UNAVAILABLE") from None
                self.sleep(2 ** attempt)
            except (ValueError, UnicodeError):
                raise SourceError("SOURCE_JSON") from None


def graphql(source, query, variables):
    result = source(query, variables)
    if not isinstance(result, dict) or result.get("errors") or not isinstance(result.get("data"), dict):
        raise SourceError("GRAPHQL_ERROR")
    return result["data"]


def identity(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise SourceError("INVALID_IDENTITY") from None


def private_file(path, value):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(value)


def manifest_file(directory, value):
    fd, name = tempfile.mkstemp(prefix=".manifest-", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, directory / "manifest.json")
    finally:
        Path(name).unlink(missing_ok=True)


def outside_git(destination):
    ancestor = destination
    while not ancestor.exists():
        ancestor = ancestor.parent
    for parent in (ancestor, *ancestor.parents):
        if os.path.lexists(parent / ".git"):
            raise SourceError("OUTPUT_IN_GIT")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["LC_ALL"] = "C"
    result = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, timeout=10, env=environment)
    if result.returncode == 0:
        raise SourceError("OUTPUT_IN_GIT")
    if result.returncode != 128 or not result.stderr.startswith(b"fatal: not a git repository (or any of the parent directories)"):
        raise SourceError("GIT_DETECTION")


def checkpoint_shape(value):
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise SourceError("RESUME_SHAPE")
    if (not isinstance(value.get("pages"), list) or
            type(value.get("issue_count")) is not int or value["issue_count"] < 0 or
            value.get("status") not in {"RUNNING", "FAILED", "COMPLETE_FOR_ISSUES"} or
            not all(isinstance(value.get(key), str) for key in ("query_sha256", "team_id", "organization_id"))):
        raise SourceError("RESUME_SHAPE")
    cursor = value.get("next_cursor")
    if cursor is not None and (not isinstance(cursor, str) or not cursor or len(cursor) > 4096):
        raise SourceError("RESUME_SHAPE")
    if not value["pages"] and cursor is not None:
        raise SourceError("RESUME_SHAPE")
    for index, record in enumerate(value["pages"], 1):
        if (not isinstance(record, dict) or record.get("file") != "page-%06d.json" % index or
                not isinstance(record.get("sha256"), str) or len(record["sha256"]) != 64 or
                any(c not in "0123456789abcdef" for c in record["sha256"]) or
                type(record.get("issue_count")) is not int or record["issue_count"] < 0):
            raise SourceError("RESUME_SHAPE")
    return value


def connection(data, team, seen, cursors):
    try:
        page = data["issues"]
        nodes, info = page["nodes"], page["pageInfo"]
        more, cursor = info["hasNextPage"], info["endCursor"]
        if not isinstance(nodes, list) or type(more) is not bool:
            raise SourceError("SOURCE_SHAPE")
        if more and (not isinstance(cursor, str) or not cursor or len(cursor) > 4096 or cursor in cursors):
            raise SourceError("CURSOR_LOOP")
        for node in nodes:
            key = identity(node["id"])
            if identity(node["team"]["id"]) != team:
                raise SourceError("TEAM_BOUNDARY")
            if key in seen:
                raise SourceError("DUPLICATE_IDENTITY")
            if not isinstance(node.get("identifier"), str) or not node["identifier"]:
                raise SourceError("SOURCE_SHAPE")
            if (node.get("labels") or {}).get("pageInfo", {}).get("hasNextPage"):
                raise SourceError("NESTED_PAGINATION")
            seen.add(key)
        if more:
            cursors.add(cursor)
        return nodes, cursor if more else None, more
    except (KeyError, TypeError, AttributeError):
        raise SourceError("SOURCE_SHAPE") from None


def boundaries(nodes, team):
    result = []
    try:
        for node in nodes:
            parent = node.get("parent")
            if parent and identity(parent["team"]["id"]) != team:
                result.append({"source_issue_id": identity(node["id"]), "entity_type": "issue",
                               "id": identity(parent["id"]), "identifier": parent["identifier"],
                               "team_id": identity(parent["team"]["id"])})
    except (KeyError, TypeError):
        raise SourceError("SOURCE_SHAPE") from None
    return result


def export_issues(source, team, destination, resume=False, max_pages=10000, max_bytes=512 * 1024 * 1024):
    team = identity(team)
    if type(max_pages) is not int or not 1 <= max_pages <= 100000:
        raise SourceError("PAGE_LIMIT")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise SourceError("EXPORT_BUDGET")
    directory = Path(destination).resolve()
    outside_git(directory)
    scope = graphql(source, SCOPE_QUERY, {"team": team})
    try:
        if identity(scope["team"]["id"]) != team:
            raise SourceError("TEAM_BOUNDARY")
        organization = identity(scope["organization"]["id"])
    except (KeyError, TypeError):
        raise SourceError("SOURCE_SHAPE") from None
    if not resume:
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    elif not directory.is_dir():
        raise SourceError("RESUME_MISSING")
    if directory.stat().st_mode & 0o077:
        raise SourceError("OUTPUT_PERMISSIONS")
    lock = os.open(str(directory / ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    manifest = None
    writable = False
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SourceError("EXPORT_LOCKED") from None
        if resume:
            saved = directory / "manifest.json"
            if saved.is_symlink() or saved.stat().st_mode & 0o077:
                raise SourceError("OUTPUT_PERMISSIONS")
            manifest = checkpoint_shape(json.loads(saved.read_text(encoding="utf-8")))
            if manifest.get("query_sha256") != QUERY_HASH or manifest.get("team_id") != team or manifest.get("organization_id") != organization:
                raise SourceError("RESUME_SCOPE")
        else:
            manifest = {"schema_version": 1, "query_sha256": QUERY_HASH, "team_id": team,
                        "organization_id": organization, "scope": scope, "pages": [], "issue_count": 0,
                        "status": "RUNNING", "atomic_snapshot": False, "categories": ["issues"], "boundary_references": [],
                        "export_started_at": datetime.now(timezone.utc).isoformat(), "next_cursor": None}
            writable = True
            manifest_file(directory, manifest)
        seen, cursors, refs = set(), set(), []
        total_bytes = 0
        more = True
        for index, record in enumerate(manifest["pages"], 1):
            if record["file"] != "page-%06d.json" % index:
                raise SourceError("RESUME_SHAPE")
            file = directory / record["file"]
            if file.is_symlink() or file.stat().st_mode & 0o077:
                raise SourceError("OUTPUT_PERMISSIONS")
            raw = file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise SourceError("CHECKSUM_MISMATCH")
            nodes, cursor, more = connection(json.loads(raw)["data"], team, seen, cursors)
            if record["issue_count"] != len(nodes):
                raise SourceError("RESUME_SHAPE")
            total_bytes += len(raw)
            refs.extend(boundaries(nodes, team))
            if not more and index != len(manifest["pages"]):
                raise SourceError("RESUME_SHAPE")
        if len(seen) != manifest["issue_count"]:
            raise SourceError("RESUME_SHAPE")
        if total_bytes > max_bytes:
            raise SourceError("EXPORT_BUDGET")
        if manifest["pages"] and cursor != manifest.get("next_cursor"):
            raise SourceError("RESUME_SHAPE")
        known = {r["file"] for r in manifest["pages"]}
        if any(p.name not in known for p in directory.glob("page-*.json")):
            raise SourceError("ORPHAN_PAGE")
        writable = True
        while more:
            if len(manifest["pages"]) >= max_pages:
                raise SourceError("PAGE_LIMIT")
            result = graphql(source, ISSUE_QUERY, {"filter": {"team": {"id": {"eq": team}}},
                                                  "cursor": manifest["next_cursor"]})
            nodes, cursor, more = connection(result, team, seen, cursors)
            refs.extend(boundaries(nodes, team))
            encoded = (json.dumps({"data": result}, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            if total_bytes + len(encoded) > max_bytes or shutil.disk_usage(directory).free < len(encoded) + 1024 ** 3:
                raise SourceError("EXPORT_BUDGET")
            page_file = directory / ("page-%06d.json" % (len(manifest["pages"]) + 1))
            private_file(page_file, encoded)
            total_bytes += len(encoded)
            manifest["pages"].append({"file": page_file.name, "sha256": hashlib.sha256(page_file.read_bytes()).hexdigest(), "issue_count": len(nodes)})
            manifest.update(issue_count=len(seen), next_cursor=cursor, status="RUNNING", boundary_references=refs)
            manifest.pop("failure_code", None)
            manifest_file(directory, manifest)
        manifest.update(status="COMPLETE_FOR_ISSUES", boundary_references=refs,
                        export_finished_at=datetime.now(timezone.utc).isoformat())
        manifest_file(directory, manifest)
        return manifest
    except (SourceError, OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, SourceError) else ("INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "EXPORT_IO_OR_SHAPE")
        if writable:
            manifest.update(status="FAILED", failure_code=code)
            manifest_file(directory, manifest)
        raise SourceError(code) from None
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", required=True, help="Immutable source team UUID")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=512 * 1024 * 1024)
    args = parser.parse_args()
    try:
        result = export_issues(LinearHTTP(os.environ.get("LINEAR_API_KEY")), args.team, args.output,
                               resume=args.resume, max_bytes=args.max_bytes)
        print(json.dumps({"status": result["status"], "issue_count": result["issue_count"], "pages": len(result["pages"])}))
        return 0
    except (SourceError, OSError, subprocess.SubprocessError, ValueError, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, SourceError) else ("INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "EXPORT_IO")
        print(json.dumps({"code": code}), file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 2


if __name__ == "__main__":
    sys.exit(main())
