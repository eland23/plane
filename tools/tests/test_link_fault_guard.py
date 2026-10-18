"""Destructive fault controls reject other targets before importing Django."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("script_name,contract", [("run_link_identity_fault.py","link"),
    ("run_link_identity_fault.py","milestone"),("run_milestone_command_fault.py","milestone")])
@pytest.mark.parametrize("url", [
    "",
    "postgresql://fixture@192.168.1.129/plane",
    "postgresql://fixture@plane-hlb464-db/plane_fixture_snapshot?host=other",
])
def test_native_fault_target_is_rejected_before_framework_or_output_setup(tmp_path,url,script_name,contract):
    script=Path(__file__).resolve().parents[2]/"apps/api/plane/tests"/script_name
    output=tmp_path/"must-not-exist"
    environment=dict(os.environ,DATABASE_URL=url)
    result=subprocess.run([sys.executable,str(script),"--contract",contract,"--output",str(output)],env=environment,
                          capture_output=True,text=True,timeout=10)
    assert result.returncode==2 and json.loads(result.stdout)=={"code":"ISOLATED_FIXTURE_REQUIRED"}
    assert not output.exists()
