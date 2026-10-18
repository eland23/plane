#!/usr/bin/env python3
"""Build release candidates without starting or deploying application services."""
import argparse
import json
import sys
import fcntl
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import threading
import signal
from contextlib import contextmanager
from pathlib import Path

TARGET = "192.168.1.130"
GIB = 1024 ** 3
SERVICES = {"api": "backend", "worker": "backend", "beat-worker": "backend",
            "migrator": "backend", "web": "frontend"}
COMMANDS = {"api": "./bin/docker-entrypoint-api.sh", "worker": "./bin/docker-entrypoint-worker.sh",
            "beat-worker": "./bin/docker-entrypoint-beat.sh", "migrator": "./bin/docker-entrypoint-migrator.sh"}


class GateError(Exception):
    def __init__(self, code):
        self.code = code


def command(argv, code="COMMAND_FAILED", timeout=60, log_path=None):
    # Never echo stderr, environment, remote URLs or credentials from tools.
    try:
        if log_path is None:
            result = subprocess.run(argv, check=True, capture_output=True, timeout=timeout)
        else:
            descriptor = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as log:
                result = subprocess.run(argv, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        raise GateError(code) from None
    return result.stdout.decode("utf-8") if result.stdout is not None else ""


def git(repo, *args):
    return command(["git", "-C", str(repo), *args], "SOURCE_CHECK").strip()


def source_identity(args):
    repo = Path(args.repo).resolve()
    if not re.fullmatch(r"[a-f0-9]{40}", args.revision):
        raise GateError("REVISION_REQUIRED")
    if not re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9/_.-]*", args.ref):
        raise GateError("REF_REQUIRED")
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise GateError("REPOSITORY_ROOT_REQUIRED")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise GateError("DIRTY_SOURCE")
    if git(repo, "rev-parse", "HEAD") != args.revision:
        raise GateError("REVISION_MISMATCH")
    remote = git(repo, "ls-remote", "--exit-code", "origin", args.ref)
    if remote.split()[0] != args.revision:
        raise GateError("UNPUSHED_REVISION")
    files = git(repo, "ls-tree", "-r", "--name-only", args.revision).splitlines()
    required = {"apps/api/Dockerfile.api", "apps/api/manage.py", "apps/web/Dockerfile.web",
                "apps/api/plane/app/views/page/wiki.py", "apps/api/plane/db/models/issue.py"}
    required.update("apps/api/" + path.removeprefix("./") for path in COMMANDS.values())
    migrations = sorted(p[len("apps/api/"):] for p in files if p.startswith("apps/api/plane/db/migrations/") and p.endswith(".py"))
    if not required.issubset(files) or not migrations:
        raise GateError("INCOMPLETE_SOURCE")
    if any(Path(p).name == ".env" or Path(p).suffix in (".pem", ".key") for p in files):
        raise GateError("TRACKED_SECRET_FILE")
    return {"revision": args.revision, "source_tree": git(repo, "rev-parse", "HEAD^{tree}"),
            "ref": args.ref, "target": args.target, "namespace": args.namespace,
            "services": SERVICES, "commands": COMMANDS, "migrations": migrations}


def preflight(args, packaging=False):
    if args.target != TARGET:
        raise GateError("TARGET_DENIED")
    if not re.fullmatch(r"plane-rehearsal-[a-z0-9][a-z0-9-]{0,39}", args.namespace):
        raise GateError("NAMESPACE_DENIED")
    report = source_identity(args)
    probe = (
        "import json,shutil; "
        "m=dict(line.split(':',1) for line in open('/proc/meminfo')); "
        "print(json.dumps(dict(disk_free=shutil.disk_usage('/var/lib/docker').free,"
        "memory_available=int(m['MemAvailable'].split()[0])*1024)))"
    )
    raw = command(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                   "-o", "StrictHostKeyChecking=yes", "root@" + TARGET,
                   "python3 -c " + shlex.quote(probe)], "TARGET_PROBE", timeout=20)
    try:
        capacity = json.loads(raw)
        if any(type(capacity[k]) is not int or capacity[k] < 0 for k in ("disk_free", "memory_available")):
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise GateError("TARGET_PROBE") from None
    # Reservation gate, not a claim of measured application requirements.
    admitted = capacity["disk_free"] >= 10 * GIB and capacity["memory_available"] >= 2 * GIB
    if not admitted and not packaging:
        raise GateError("TARGET_CAPACITY")
    report.update(status="PACKAGING_ONLY" if packaging else "PASS", capacity=capacity,
                  runtime_admission={"status": "PASS"} if admitted else {"status": "BLOCKED", "code": "TARGET_CAPACITY"},
                  reservation={"disk_bytes": 10 * GIB, "memory_bytes": 2 * GIB})
    return report


@contextmanager
def release_lock():
    path = Path(tempfile.gettempdir()) / "plane-release-192.168.1.130.lock"
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise GateError("RELEASE_LOCKED") from None
        yield
    finally:
        os.close(fd)
    # Do not unlink a lock inode: contenders must always lock the same file.


def stream_timer(proc, timeout):
    expired = threading.Event()

    def stop():
        # A child may keep the pipe open after its leader exits.
        expired.set()
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    timer = threading.Timer(timeout, stop)
    timer.daemon = True
    timer.start()
    return expired, timer


def backend_inventory(repo, revision):
    inventory = {}
    entries = git(repo, "ls-tree", "-rz", revision, "--", "apps/api/").split("\0")
    for entry in entries:
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        relative = path.removeprefix("apps/api/")
        if relative.startswith(("plane/", "bin/", "templates/", "requirements/")) or relative in ("manage.py", "package.json", "requirements.txt"):
            mode, kind, blob = metadata.split()
            if kind != "blob" or mode not in ("100644", "100755"):
                raise GateError("UNSUPPORTED_SOURCE")
            inventory[relative] = blob
    return inventory


def snapshot(repo, revision, destination, timeout=120):
    # Git blob identities are independent of archive attributes/output.
    inventory = backend_inventory(repo, revision)
    proc = subprocess.Popen(["git", "-C", str(repo), "archive", revision], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    expired, timer = stream_timer(proc, timeout)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
            for member in archive:
                path = destination / member.name
                if not path.resolve().is_relative_to(destination):
                    raise GateError("ARCHIVE_PATH")
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as src, path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    path.chmod(member.mode & 0o777)
                elif member.issym():
                    if not (path.parent / member.linkname).resolve().is_relative_to(destination):
                        raise GateError("ARCHIVE_PATH")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.symlink_to(member.linkname)
                else:
                    raise GateError("ARCHIVE_PATH")
        if proc.wait(timeout=60) != 0:
            raise GateError("SOURCE_ARCHIVE")
    except tarfile.TarError:
        raise GateError("SOURCE_ARCHIVE") from None
    finally:
        timer.cancel()
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        proc.stdout.close()
        if expired.is_set():
            raise GateError("STREAM_TIMEOUT")
    expected = {}
    for relative, blob in inventory.items():
        file = destination / "apps/api" / relative
        if not file.is_file() or file.is_symlink():
            raise GateError("ARCHIVE_CONTENT")
        content = file.read_bytes()
        git_hash = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if git_hash != blob:
            raise GateError("ARCHIVE_CONTENT")
        expected["code/" + relative] = hashlib.sha256(content).hexdigest()
    return expected


def image_identity(tag, revision, tree, backend=False):
    try:
        image = json.loads(command(["docker", "image", "inspect", tag], "IMAGE_INSPECT"))[0]
        labels = image["Config"]["Labels"]
        if labels["org.opencontainers.image.revision"] != revision or labels["io.plane.source.tree"] != tree:
            raise GateError("IMAGE_IDENTITY")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image["Id"]):
            raise GateError("IMAGE_IDENTITY")
        if backend and (image["Config"].get("WorkingDir") != "/code" or image["Config"].get("Cmd") != [COMMANDS["api"]]):
            raise GateError("IMAGE_COMMAND")
    except (ValueError, TypeError, KeyError, IndexError):
        raise GateError("IMAGE_IDENTITY") from None
    return image["Id"]


def image_backend_files(tag, expected, timeout=120):
    """Inspect saved layers offline; never create/start an application container."""
    proc = subprocess.Popen(["docker", "image", "save", tag], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    expired, timer = stream_timer(proc, timeout)
    layers = {}
    manifest = None
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                if member.name == "manifest.json":
                    manifest = json.load(archive.extractfile(member))
                elif member.name.endswith(".tar") or member.name.startswith("blobs/sha256/"):
                    changes = {"remove": [], "files": {}}
                    try:
                        layer = tarfile.open(fileobj=archive.extractfile(member), mode="r|*")
                    except tarfile.TarError:
                        # OCI exports also contain config/manifest JSON blobs.
                        # Missing or malformed referenced layers fail below.
                        continue
                    with layer:
                        for entry in layer:
                            name = entry.name.removeprefix("./").lstrip("/")
                            if Path(name).name.startswith(".wh."):
                                parent, _, leaf = name.rpartition("/")
                                prefix = (parent + "/") if parent else ""
                                changes["remove"].append(prefix if leaf == ".wh..wh..opq" else prefix + leaf[4:])
                            elif entry.isfile() and name in expected:
                                executable = name in {"code/" + value.removeprefix("./") for value in COMMANDS.values()}
                                changes["files"][name] = (None if executable and not entry.mode & 0o111
                                                          else hashlib.sha256(layer.extractfile(entry).read()).hexdigest())
                            elif entry.isfile() and any(path.startswith(name.rstrip("/") + "/") for path in expected):
                                changes["remove"].append(name)
                            elif entry.issym() or entry.islnk() or (not entry.isfile() and name in expected):
                                changes["remove"].append(name)
                    layers[member.name] = changes
        if proc.wait(timeout=60) != 0 or not manifest or len(manifest) != 1:
            raise GateError("IMAGE_CONTENT")
        actual = {}
        for name in manifest[0]["Layers"]:
            if name not in layers:
                raise GateError("IMAGE_CONTENT")
            # Whiteouts affect lower layers, never files added in this layer.
            for prefix in layers[name]["remove"]:
                actual = {k: v for k, v in actual.items()
                          if prefix and k != prefix and not k.startswith(prefix.rstrip("/") + "/")}
            actual.update(layers[name]["files"])
        if any(actual.get(k) != v for k, v in expected.items()):
            raise GateError("IMAGE_CONTENT")
    except (tarfile.TarError, ValueError, KeyError, TypeError):
        raise GateError("IMAGE_CONTENT") from None
    finally:
        timer.cancel()
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        proc.stdout.close()
        if expired.is_set():
            raise GateError("STREAM_TIMEOUT")


def pin_dockerfile(file, replacements):
    text = file.read_text()
    for old, new in replacements.items():
        if text.count("FROM " + old + " ") + text.count("FROM " + old + "\n") != 1:
            raise GateError("DOCKERFILE_COMPATIBILITY")
        text = text.replace("FROM " + old, "FROM " + new, 1)
    aliases = set()
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0].upper() == "FROM":
            if len(parts) < 2 or (parts[1] not in aliases and not re.fullmatch(r"[a-z]+@sha256:[a-f0-9]{64}", parts[1])):
                raise GateError("BASE_DIGEST_REQUIRED")
            if len(parts) == 4 and parts[2].upper() == "AS":
                aliases.add(parts[3])
    file.write_text(text)


def build(args, report):
    if not args.output or not args.python_base or not args.node_base or not args.nginx_base:
        raise GateError("BUILD_ARGUMENTS")
    for value, name in [(args.python_base, "python"), (args.node_base, "node"), (args.nginx_base, "nginx")]:
        if not re.fullmatch(name + r"@sha256:[a-f0-9]{64}", value):
            raise GateError("BASE_DIGEST_REQUIRED")
    output = Path(args.output).resolve()
    repo = Path(args.repo).resolve()
    if output.is_relative_to(repo) or output.exists():
        raise GateError("OUTPUT_DENIED")
    if shutil.disk_usage(tempfile.gettempdir()).free < 10 * GIB:
        raise GateError("BUILD_CAPACITY")
    logs = output.with_name(output.name + ".build-logs")
    logs.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix="plane-source-") as directory:
        source = Path(directory)
        expected = snapshot(repo, args.revision, source)
        backend = source / "apps/api"
        dockerfile = backend / "Dockerfile.api"
        if "COPY plane plane/" not in dockerfile.read_text():
            raise GateError("DOCKERFILE_COMPATIBILITY")
        pin_dockerfile(dockerfile, {"python:3.12.10-alpine": args.python_base})
        webfile = source / "apps/web/Dockerfile.web"
        pin_dockerfile(webfile, {"node:22-alpine": args.node_base, "nginx:1.31-alpine": args.nginx_base})
        images = {}
        for kind, context, file in [("backend", backend, dockerfile), ("frontend", source, webfile)]:
            tag = args.namespace + "-" + kind + ":" + args.revision
            # Logs may include dependency URLs; keep them private, do not echo them.
            command(["docker", "build", "--pull", "--label", "org.opencontainers.image.revision=" + args.revision,
                     "--label", "io.plane.source.tree=" + report["source_tree"], "--tag", tag,
                     "--file", str(file), str(context)], "IMAGE_BUILD", timeout=3600, log_path=logs / (kind + ".log"))
            images[kind] = {"tag": tag, "id": image_identity(tag, args.revision, report["source_tree"], backend=kind == "backend")}
        image_backend_files(images["backend"]["id"], expected)
        # Refuse publication if source or remote ref changed while building.
        source_identity(args)
        report.update(images=images, python_base=args.python_base, node_base=args.node_base, nginx_base=args.nginx_base,
                      verified_backend_files=len(expected), schema_version=1)
        with output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "build", "preflight-package", "package"])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output")
    parser.add_argument("--python-base")
    parser.add_argument("--node-base")
    parser.add_argument("--nginx-base")
    args = parser.parse_args()
    try:
        report = preflight(args, packaging=args.command in {"preflight-package", "package"})
        if args.command in {"build", "package"}:
            with release_lock():
                report = build(args, report)
        print(json.dumps(report, sort_keys=True))
    except (GateError, OSError, subprocess.SubprocessError, UnicodeError) as error:
        print(json.dumps({"code": error.code if isinstance(error, GateError) else "LOCAL_IO"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
