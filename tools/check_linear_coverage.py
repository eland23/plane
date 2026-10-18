#!/usr/bin/env python3
"""Retain clean passes around field-loss and edge-loss failure controls."""
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
        ("failure-modified-field", "    removed_edges, added_edges = sorted(before['edges'] - after['edges']), sorted(after['edges'] - before['edges'])",
         "    modified = []\n    removed_edges, added_edges = sorted(before['edges'] - after['edges']), sorted(after['edges'] - before['edges'])",
         "concurrent_edit_archive"),
        ("failure-removed-edge", "    schema_added = sorted(set(after['schema_fields']) - set(before['schema_fields']))",
         "    removed_edges = []\n    schema_added = sorted(set(after['schema_fields']) - set(before['schema_fields']))",
         "missing_document_edge"),
        ("restore-and-repeat", None, None, None),
    ]
    receipts = []
    for name, old, new, selection in cases:
        with tempfile.TemporaryDirectory(prefix="linear-coverage-contract-") as directory:
            root = Path(directory)
            (root / "tools/tests").mkdir(parents=True)
            source = (tools / "linear_coverage.py").read_text()
            if old:
                if source.count(old) != 1:
                    raise RuntimeError("Failure boundary must match exactly once")
                source = source.replace(old, new)
            (root / "tools/linear_coverage.py").write_text(source)
            shutil.copyfile(tools / "tests/test_linear_coverage.py", root / "tools/tests/test_linear_coverage.py")
            shutil.copyfile(tools / "linear_export.py", root / "tools/linear_export.py")
            shutil.copyfile(tools / "linear_associations.py", root / "tools/linear_associations.py")
            shutil.copyfile(tools / "tests/test_linear_associations.py", root / "tools/tests/test_linear_associations.py")
            command = [sys.executable, "-m", "pytest", "-q", "tools/tests/test_linear_coverage.py", "-o", "addopts=",
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
