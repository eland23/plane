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
        ("failure-owned-helper-cleanup", "os.killpg(process.pid, signal.SIGKILL)", "probe_error_terminates", "pass"),
        ("failure-private-output", "    require_private_output(output, repo)\n", "denies_logs_inside_any_git", "    pass\n"),
        ("restore-and-repeat", None, None, None),
    ]
    cases = [(*case, "tools/plane_release.py") for case in cases]
    native = root.parent / "docs/verification/HLB-433/native"
    seed = (native / "seed_schema_fixture.py").read_text()
    admission = seed[seed.index("NS ="):seed.index("import django")]
    cases[-1:-1] = [
        ("failure-seed-admission", admission, "seed_rejects_nonfixture_database", "", "docs/verification/HLB-433/native/seed_schema_fixture.py"),
        ("failure-inspection-admission", "    require(listing.returncode==0, 'INSPECTION_FAILED')", "inspection_failure_preserves", "    if listing.returncode: return None", "docs/verification/HLB-433/native/schema_api_fixture.py"),
        ("failure-receipt-cleanup", "            finally:\n                cleanup()", "receipt_failure_still_cleans", "            except OSError:\n                raise\n            cleanup()", "docs/verification/HLB-433/native/schema_api_fixture.py"),
        ("failure-lease-cleanup", "    finally:\n        os.close(lease)", "receipt_failure_still_cleans", "    finally:\n        pass", "docs/verification/HLB-433/native/schema_api_fixture.py"),
    ]
    for name, defect, selection, replacement, target in cases:
        with tempfile.TemporaryDirectory(prefix="plane-contract-", dir="/var/tmp") as temporary:
            clone = Path(temporary)
            (clone / "tools/tests").mkdir(parents=True)
            files = ["tools/plane_release.py", "tools/tests/test_plane_release.py",
                     "tools/tests/test_native_backend_probe_guard.py", "tools/tests/test_schema_fixture_safety.py"]
            files += ["docs/verification/HLB-433/native/" + file.name for file in native.glob("*.py")]
            for file in files:
                destination = clone / file
                destination.parent.mkdir(parents=True, exist_ok=True)
                text = (root.parent / file).read_text()
                if defect and file == target:
                    if text.count(defect) != 1:
                        raise RuntimeError("Fault boundary must match exactly once")
                    text = text.replace(defect, replacement if replacement is not None else "if False:")
                destination.write_text(text)
            command = [sys.executable, "-m", "pytest", "-q", "tools/tests/test_plane_release.py", "tools/tests/test_native_backend_probe_guard.py",
                       "tools/tests/test_schema_fixture_safety.py", "-o", "addopts=", "--junitxml=" + str(output / (name + ".xml")),
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
    return 0 if len(runs) == 11 and all(r["accepted"] and r["fixture_directory_removed"] for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
