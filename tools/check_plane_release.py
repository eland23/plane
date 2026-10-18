#!/usr/bin/env python3
"""Save two clean passes around bounded defects; no services are started."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent
    runs = []
    cases = [
        ("pass-known-state", None, None, None),
        ("failure-target-guard", "if args.target != TARGET:", "release_preflight_rejects_wrong_target", None),
        ("failure-image-integrity", "if any(actual.get(k) != v for k, v in expected.items()):", "detects_missing_or_changed_migration", None),
        ("failure-packaging-admission", 'status="PACKAGING_ONLY" if packaging else "PASS"', "package_preflight_reports", 'status="PASS"'),
        ("restore-and-repeat", None, None, None),
    ]
    for name, defect, selection, replacement in cases:
        with tempfile.TemporaryDirectory(prefix="plane-contract-") as temporary:
            clone = Path(temporary)
            (clone / "tools/tests").mkdir(parents=True)
            text = (root / "plane_release.py").read_text()
            if defect:
                if text.count(defect) != 1:
                    raise RuntimeError("Fault boundary must match exactly once")
                text = text.replace(defect, replacement or "if False:")
            (clone / "tools/plane_release.py").write_text(text)
            shutil.copyfile(root / "tests/test_plane_release.py", clone / "tools/tests/test_plane_release.py")
            command = [sys.executable, "-m", "pytest", "-q", "tools/tests/test_plane_release.py",
                       "-o", "addopts=", "--junitxml=" + str(output / (name + ".xml")),
                       "--basetemp=" + str(clone / "fixtures")]
            if selection:
                command += ["-k", selection]
            result = subprocess.run(command, cwd=clone, text=True, capture_output=True, timeout=180)
            log = result.stdout + result.stderr
            (output / (name + ".log")).write_text(log)
            expected_exit = result.returncode == 1 and "AssertionError" in log if defect else result.returncode == 0
            # pytest.raises failures have a distinct, checkable assertion message.
            if defect and "DID NOT RAISE" in log and result.returncode == 1:
                expected_exit = True
            runs.append({"run": name, "exit": result.returncode, "expected_failure": bool(defect), "accepted": expected_exit})
        runs[-1]["fixture_directory_removed"] = not clone.exists()
        if not runs[-1]["accepted"]:
            break
    (output / "receipts.json").write_text(json.dumps(runs, indent=2) + "\n")
    print(json.dumps(runs))
    return 0 if len(runs) == 5 and all(r["accepted"] and r["fixture_directory_removed"] for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
