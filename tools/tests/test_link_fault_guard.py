"""Destructive fault controls reject other targets before importing Django."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("contract", ["link", "milestone"])
@pytest.mark.parametrize("url", [
    "",
    "postgresql://fixture@192.168.1.129/plane",
    "postgresql://fixture@plane-hlb464-db/plane_fixture_snapshot?host=other",
])
def test_native_fault_target_is_rejected_before_framework_or_output_setup(tmp_path,url,contract):
    script=Path(__file__).resolve().parents[2]/"apps/api/plane/tests/run_link_identity_fault.py"
    output=tmp_path/"must-not-exist"
    environment=dict(os.environ,DATABASE_URL=url)
    result=subprocess.run([sys.executable,str(script),"--contract",contract,"--output",str(output)],env=environment,
                          capture_output=True,text=True,timeout=10)
    assert result.returncode==2 and json.loads(result.stdout)=={"code":"ISOLATED_FIXTURE_REQUIRED"}
    assert not output.exists()
