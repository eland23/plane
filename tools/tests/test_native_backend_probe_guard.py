"""Optimized execution must fail before any Docker/network operation."""
from pathlib import Path
import subprocess
import sys

import pytest

PROBE = Path(__file__).resolve().parents[2] / 'docs/verification/HLB-433/native/backend_command_probe.py'


@pytest.mark.parametrize('mode', ['flag', 'environment'])
def test_optimized_probe_cannot_reach_external_commands(tmp_path, mode):
    marker = tmp_path / 'external-command-called'
    binary = tmp_path / 'bin'
    binary.mkdir()
    for name in ['ip', 'docker']:
        file = binary / name
        file.write_text('#!' + sys.executable + '\nfrom pathlib import Path\n'
            + f'Path({str(marker)!r}).touch()\nprint("[]")\n')
        file.chmod(0o755)
    env = {'PATH': str(binary), **({'PYTHONOPTIMIZE': '1'} if mode == 'environment' else {})}
    result = subprocess.run([sys.executable, *(['-O'] if mode == 'flag' else []), str(PROBE)],
        capture_output=True, text=True, env=env, timeout=10)
    assert result.returncode == 2
    assert result.stderr.strip() == 'OPTIMIZED_EXECUTION_DENIED'
    assert not marker.exists()
