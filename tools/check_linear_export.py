#!/usr/bin/env python3
"""Retain clean passes around data-loss and checksum failure controls."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    tools = Path(__file__).resolve().parent
    cases = [
        ("pass-known-state", None, None, None),
        ("failure-page-loss", "nodes, cursor, more = connection(result, team, seen, cursors)",
         "nodes, cursor, more = connection(result, team, seen, cursors)\n            more, cursor = False, None",
         "retains_every_page_and_archived_payload"),
        ("failure-checksum", 'if hashlib.sha256(raw).hexdigest() != record["sha256"]:',
         "if False:", "resume_detects_tampering_and_scope_changes"),
        ("restore-and-repeat", None, None, None),
    ]
    receipts = []
    for name, old, new, selection in cases:
        with tempfile.TemporaryDirectory(prefix="linear-export-contract-") as directory:
            root = Path(directory)
            (root / "tools/tests").mkdir(parents=True)
            source = (tools / "linear_export.py").read_text()
            if old:
                if source.count(old) != 1:
                    raise RuntimeError("Failure boundary must match exactly once")
                source = source.replace(old, new)
            (root / "tools/linear_export.py").write_text(source)
            shutil.copyfile(tools / "tests/test_linear_export.py", root / "tools/tests/test_linear_export.py")
            command = [sys.executable, "-m", "pytest", "-q", "tools/tests/test_linear_export.py", "-o", "addopts=",
                       "--basetemp=" + str(root / "fixtures"), "--junitxml=" + str(output / (name + ".xml"))]
            if selection:
                command += ["-k", selection]
            result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=120)
            log = result.stdout + result.stderr
            (output / (name + ".log")).write_text(log)
            accepted = result.returncode == 0 if not old else (result.returncode == 1 and ("AssertionError" in log or "DID NOT RAISE" in log))
            receipts.append({"run": name, "exit": result.returncode, "expected_failure": bool(old), "accepted": accepted})
        receipts[-1]["fixtures_removed"] = not root.exists()
        if not accepted:
            break
    (output / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts))
    return 0 if len(receipts) == 4 and all(r["accepted"] and r["fixtures_removed"] for r in receipts) else 1


if __name__ == "__main__":
    sys.exit(main())
