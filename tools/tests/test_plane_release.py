"""Public release-candidate CLI contracts; no application services run here."""
import subprocess
import sys
import json
import os
import fcntl
import hashlib
import io
import tarfile
import importlib.util
import uuid
import time
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parents[1] / "plane_release.py"


def test_release_preflight_rejects_wrong_target_before_any_work(tmp_path):
    result = subprocess.run(
        [sys.executable, str(CLI), "preflight", "--repo", str(tmp_path),
         "--revision", "a" * 40, "--ref", "refs/heads/test",
         "--namespace", "plane-rehearsal-test", "--target", "192.168.1.129"],
        text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert '"code": "TARGET_DENIED"' in result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def source(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "candidate", str(repo)], check=True, capture_output=True)
    files = {
        "apps/api/Dockerfile.api": "FROM python:3.12.10-alpine\nCOPY plane plane/\n",
        "apps/api/manage.py": "# manage\n",
        "apps/api/plane/db/migrations/0001_initial.py": "# synthetic migration\n",
        "apps/api/plane/db/models/issue.py": "# synthetic model\n",
        "apps/api/plane/app/views/page/wiki.py": "# synthetic wiki\n",
        "apps/web/Dockerfile.web": "FROM node:22-alpine AS base\nCOPY . .\n",
        "apps/api/bin/docker-entrypoint-api.sh": "#!/bin/sh\n",
        "apps/api/bin/docker-entrypoint-worker.sh": "#!/bin/sh\n# worker\n",
        "apps/api/bin/docker-entrypoint-beat.sh": "#!/bin/sh\n# beat\n",
        "apps/api/bin/docker-entrypoint-migrator.sh": "#!/bin/sh\n# migrate\n",
    }
    for name, content in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", "candidate")
    binary = tmp_path / "bin"
    binary.mkdir()
    probe = binary / "ssh"
    probe.write_text("#!/usr/bin/env python3\nimport os\nprint(os.environ.get('PROBE', '{\"disk_free\": 107374182400, \"memory_available\": 8589934592}'))\n")
    probe.chmod(0o755)
    # Fixture reprs can appear in failure receipts; never carry real secrets.
    env = {"PATH": str(binary) + os.pathsep + os.environ["PATH"], "TMPDIR": str(tmp_path),
           "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    return repo, env


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


def invoke(source, command="preflight", **changes):
    repo, env = source
    args = {"repo": str(repo), "revision": git(repo, "rev-parse", "HEAD"),
            "ref": "refs/heads/candidate", "namespace": "plane-rehearsal-test", "target": "192.168.1.130", **changes}
    result = subprocess.run([sys.executable, str(CLI), command, *[v for k, val in args.items() for v in ("--" + k, val)]],
                            text=True, capture_output=True, env=env, timeout=20)
    return result


def test_release_preflight_reports_complete_shared_backend_identity(source):
    result = invoke(source)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "PASS"
    assert report["services"] == {"api": "backend", "worker": "backend", "beat-worker": "backend", "migrator": "backend", "web": "frontend"}
    assert report["migrations"] == ["plane/db/migrations/0001_initial.py"]
    assert report["commands"] == {
        "api": "./bin/docker-entrypoint-api.sh", "worker": "./bin/docker-entrypoint-worker.sh",
        "beat-worker": "./bin/docker-entrypoint-beat.sh", "migrator": "./bin/docker-entrypoint-migrator.sh"}
    assert report["revision"] == git(source[0], "rev-parse", "HEAD")
    assert git(source[0], "status", "--porcelain") == ""


@pytest.mark.parametrize("dirty", ["modified", "untracked"])
def test_release_preflight_rejects_dirty_source(source, dirty):
    repo, _ = source
    p = repo / ("apps/api/manage.py" if dirty == "modified" else "unexpected.txt")
    p.write_text("dirty")
    result = invoke(source)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "DIRTY_SOURCE"


def test_release_preflight_rejects_unpushed_commit(source):
    repo, _ = source
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "unpushed")
    result = invoke(source)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "UNPUSHED_REVISION"


@pytest.mark.parametrize("namespace", ["plane-app", "fashionfindr-live", "plane-rehearsal-../unsafe"])
def test_release_preflight_rejects_shared_or_invalid_namespace(source, namespace):
    result = invoke(source, namespace=namespace)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "NAMESPACE_DENIED"


def test_release_preflight_fails_closed_on_target_capacity_and_recovers(source):
    source[1]["PROBE"] = '{"disk_free": 1048576, "memory_available": 1048576}'
    result = invoke(source)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "TARGET_CAPACITY"
    del source[1]["PROBE"]
    assert invoke(source).returncode == 0


def test_release_preflight_rejects_malformed_probe_without_leaking_output(source):
    source[1]["PROBE"] = "private-probe-fixture"
    result = invoke(source)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "TARGET_PROBE"
    assert "private-probe-fixture" not in result.stderr


def test_release_preflight_rejects_mismatched_revision(source):
    result = invoke(source, revision="b" * 40)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "REVISION_MISMATCH"


def test_build_rejects_a_concurrent_candidate_before_docker(source, tmp_path):
    with (tmp_path / "plane-release-192.168.1.130.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = invoke(source, command="build")
        assert result.returncode == 2
        assert json.loads(result.stderr)["code"] == "RELEASE_LOCKED"


@pytest.fixture
def release_module():
    spec = importlib.util.spec_from_file_location("plane_release", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tar_bytes(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, content in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    return output.getvalue()


@pytest.fixture
def image_cli(tmp_path, monkeypatch):
    binary = tmp_path / "docker"
    binary.write_text("#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nif sys.argv[1:3]==['image','save']:\n sys.stdout.buffer.write(Path(os.environ['IMAGE_TAR']).read_bytes())\nelse:\n print(os.environ['IMAGE_INSPECT'])\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    return tmp_path, monkeypatch


def test_complete_image_manifest_rejects_mixed_revisions(release_module, image_cli):
    _, env = image_cli
    env.setenv("IMAGE_INSPECT", json.dumps([{"Id": "sha256:" + "d" * 64, "Config": {"Labels": {
        "org.opencontainers.image.revision": "b" * 40, "io.plane.source.tree": "c" * 40}}}]))
    with pytest.raises(release_module.GateError, match="IMAGE_IDENTITY"):
        release_module.image_identity("fixture", "a" * 40, "c" * 40)
    env.setenv("IMAGE_INSPECT", json.dumps([{"Id": "sha256:" + "d" * 64, "Config": {"Labels": {
        "org.opencontainers.image.revision": "a" * 40, "io.plane.source.tree": "c" * 40}}}]))
    assert release_module.image_identity("fixture", "a" * 40, "c" * 40) == "sha256:" + "d" * 64


@pytest.mark.parametrize("defect", ["missing", "changed", "whiteout"])
def test_complete_image_manifest_detects_missing_or_changed_migration(release_module, image_cli, defect):
    tmp, env = image_cli
    name = "code/plane/db/migrations/0001_initial.py"
    correct = b"# synthetic migration\n"
    lower = tar_bytes({name: correct})
    upper = tar_bytes({name: b"wrong"} if defect == "changed" else
                      {"code/plane/db/migrations/.wh.0001_initial.py": b""} if defect == "whiteout" else {})
    layers = {"first/layer.tar": lower, "second/layer.tar": upper}
    if defect == "missing":
        layers["first/layer.tar"] = tar_bytes({})
    manifest = json.dumps([{"Layers": list(layers)}]).encode()
    archive = tmp / "image.tar"
    archive.write_bytes(tar_bytes({**layers, "manifest.json": manifest}))
    env.setenv("IMAGE_TAR", str(archive))
    with pytest.raises(release_module.GateError, match="IMAGE_CONTENT"):
        release_module.image_backend_files("fixture", {name: hashlib.sha256(correct).hexdigest()})
    archive.write_bytes(tar_bytes({"first/layer.tar": lower, "manifest.json": json.dumps([{"Layers": ["first/layer.tar"]}]).encode()}))
    release_module.image_backend_files("fixture", {name: hashlib.sha256(correct).hexdigest()})


def test_build_refuses_mutable_base_tags(source, tmp_path):
    result = invoke(source, command="build", output=str(tmp_path / "manifest.json"),
                    **{"python-base": "python:latest", "node-base": "node:latest", "nginx-base": "nginx:latest"})
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "BASE_DIGEST_REQUIRED"
    assert not (tmp_path / "manifest.json").exists()


def test_complete_image_manifest_detects_file_replaced_by_symlink(release_module, image_cli):
    tmp, env = image_cli
    name = "code/plane/db/migrations/0001_initial.py"
    correct = b"# synthetic migration\n"
    upper = io.BytesIO()
    with tarfile.open(fileobj=upper, mode="w") as layer:
        link = tarfile.TarInfo(name)
        link.type = tarfile.SYMTYPE
        link.linkname = "/tmp/not-a-migration"
        layer.addfile(link)
    layers = {"first/layer.tar": tar_bytes({name: correct}), "second/layer.tar": upper.getvalue()}
    archive = tmp / "image.tar"
    archive.write_bytes(tar_bytes({**layers, "manifest.json": json.dumps([{"Layers": list(layers)}]).encode()}))
    env.setenv("IMAGE_TAR", str(archive))
    with pytest.raises(release_module.GateError, match="IMAGE_CONTENT"):
        release_module.image_backend_files("fixture", {name: hashlib.sha256(correct).hexdigest()})


def test_complete_image_manifest_reads_real_docker_export_without_starting_container(release_module, tmp_path):
    tag = "plane-release-test:" + uuid.uuid4().hex
    content = b"synthetic migration format check\n"
    (tmp_path / "marker").write_bytes(content)
    (tmp_path / "Dockerfile").write_text("FROM scratch\nCOPY marker /code/plane/db/migrations/fixture.py\n")
    try:
        subprocess.run(["docker", "build", "-t", tag, str(tmp_path)], check=True, capture_output=True, timeout=60)
        release_module.image_backend_files(tag, {"code/plane/db/migrations/fixture.py": hashlib.sha256(content).hexdigest()})
    finally:
        subprocess.run(["docker", "image", "rm", tag], capture_output=True, timeout=30)


def test_complete_image_manifest_rejects_ancestor_replaced_by_regular_file(release_module, image_cli):
    tmp, env = image_cli
    name = "code/plane/db/migrations/fixture.py"
    content = b"fixture"
    layers = {"first/layer.tar": tar_bytes({name: content}), "second/layer.tar": tar_bytes({"code/plane": b"not a directory"})}
    archive = tmp / "image.tar"
    archive.write_bytes(tar_bytes({**layers, "manifest.json": json.dumps([{"Layers": list(layers)}]).encode()}))
    env.setenv("IMAGE_TAR", str(archive))
    with pytest.raises(release_module.GateError, match="IMAGE_CONTENT"):
        release_module.image_backend_files("fixture", {name: hashlib.sha256(content).hexdigest()})


def test_candidate_snapshot_rejects_export_ignored_migration(release_module, source, tmp_path):
    repo, _ = source
    (repo / ".gitattributes").write_text("apps/api/plane/db/migrations/0001_initial.py export-ignore\n")
    git(repo, "add", ".gitattributes")
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "exclude migration")
    git(repo, "push", "origin", "candidate")
    destination = tmp_path / "snapshot"
    destination.mkdir()
    with pytest.raises(release_module.GateError, match="ARCHIVE_CONTENT"):
        release_module.snapshot(repo, git(repo, "rev-parse", "HEAD"), destination)


def test_saved_image_stream_timeout_kills_and_reaps_its_process(release_module, image_cli):
    tmp, _ = image_cli
    (tmp / "docker").write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n")
    started = time.monotonic()
    with pytest.raises(release_module.GateError, match="STREAM_TIMEOUT"):
        release_module.image_backend_files("fixture", {}, timeout=0.1)
    assert time.monotonic() - started < 3


def test_saved_image_deadline_cleans_child_after_leader_exits(release_module, image_cli):
    tmp, _ = image_cli
    pidfile = tmp / "child-pid"
    (tmp / "docker").write_text(
        "#!/usr/bin/env python3\nimport subprocess,sys\nfrom pathlib import Path\n"
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(4)'])\n"
        + "Path(" + repr(str(pidfile)) + ").write_text(str(p.pid))\n")
    started = time.monotonic()
    with pytest.raises(release_module.GateError, match="STREAM_TIMEOUT"):
        release_module.image_backend_files("fixture", {}, timeout=1.0)
    assert time.monotonic() - started < 3
    child_stat = Path("/proc") / pidfile.read_text() / "stat"
    try:
        assert child_stat.read_text().split()[2] == "Z"
    except FileNotFoundError:
        pass


def test_dockerfile_pins_every_external_stage(release_module, tmp_path):
    file = tmp_path / "Dockerfile"
    file.write_text("FROM node:22-alpine AS base\nFROM base AS builder\nFROM nginx:1.31-alpine AS production\n")
    release_module.pin_dockerfile(file, {"node:22-alpine": "node@sha256:" + "a" * 64,
                                       "nginx:1.31-alpine": "nginx@sha256:" + "b" * 64})
    assert "FROM node@sha256:" + "a" * 64 + " AS base" in file.read_text()
    assert "FROM nginx@sha256:" + "b" * 64 + " AS production" in file.read_text()
    assert "FROM base AS builder" in file.read_text()
    file.write_text("FROM node:22-alpine AS base\nFROM redis:latest AS surprise\n")
    with pytest.raises(release_module.GateError, match="BASE_DIGEST_REQUIRED"):
        release_module.pin_dockerfile(file, {"node:22-alpine": "node@sha256:" + "a" * 64})


def test_backend_command_identity_cannot_pass_with_wrong_entrypoint(release_module, image_cli):
    _, env = image_cli
    env.setenv("IMAGE_INSPECT", json.dumps([{"Id": "sha256:" + "d" * 64, "Config": {
        "Labels": {"org.opencontainers.image.revision": "a" * 40, "io.plane.source.tree": "c" * 40},
        "WorkingDir": "/code", "Cmd": ["/bin/false"]}}]))
    with pytest.raises(release_module.GateError, match="IMAGE_COMMAND"):
        release_module.image_identity("fixture", "a" * 40, "c" * 40, backend=True)
