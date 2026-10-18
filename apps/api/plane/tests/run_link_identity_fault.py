"""Prove that unchanged native assertions detect a missing replay-identity constraint.

Run only in the isolated .130 runner, against its synthetic snapshot fixture.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import django


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    django.setup()
    from django.conf import settings
    import psycopg
    config = settings.DATABASES["default"]
    if config["HOST"] != "plane-hlb464-db" or config["NAME"] != "plane_fixture_snapshot":
        raise RuntimeError("Isolated fixture database required")
    command = [
        sys.executable, "-m", "pytest",
        "plane/tests/contract/test_import_link_identity.py",
        "-k", "import_link_identity_is_scoped_unique",
        "-q", "-o", "addopts=", "-p", "no:cacheprovider", "--reuse-db", "--migrations",
        "--junitxml=" + str(output / "failure-identity-loss.xml"),
    ]
    with psycopg.connect(
        host=config["HOST"], port=config.get("PORT") or 5432,
        user=config["USER"], password=config["PASSWORD"],
        dbname="test_" + config["NAME"], autocommit=True,
    ) as database:
        with database.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.issue_links")
            if cursor.fetchone()[0] != 0:
                raise RuntimeError("Expected empty synthetic link fixture")
            cursor.execute(
                "ALTER TABLE public.issue_links DROP CONSTRAINT issue_link_source_identity_unique"
            )
            restored = False
            try:
                run = subprocess.run(command, text=True, capture_output=True, timeout=180)
                log = run.stdout + run.stderr
                (output / "failure-identity-loss.log").write_text(log)
            finally:
                cursor.execute(
                    "ALTER TABLE public.issue_links ADD CONSTRAINT issue_link_source_identity_unique "
                    "UNIQUE (workspace_id, external_source, external_id)"
                )
                cursor.execute(
                    "SELECT count(*) FROM pg_constraint WHERE conrelid='public.issue_links'::regclass "
                    "AND conname='issue_link_source_identity_unique'"
                )
                restored = cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM public.issue_links")
            rows_after = cursor.fetchone()[0]
    suites = ET.parse(output / "failure-identity-loss.xml").getroot().findall("testsuite")
    intended = (
        run.returncode == 1 and "DID NOT RAISE" in log
        and sum(int(s.get("tests", 0)) for s in suites) == 1
        and sum(int(s.get("failures", 0)) for s in suites) == 1
        and sum(int(s.get("errors", 0)) for s in suites) == 0
    )
    receipt = {
        "exit": run.returncode, "expected_failure": True, "intended_assertion_detected": intended,
        "constraint_restored": restored, "fixture_link_rows_after": rows_after,
        "accepted": intended and restored and rows_after == 0,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    return 0 if receipt["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
