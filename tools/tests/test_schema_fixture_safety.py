"""Fixture guards and cleanup at filesystem/Docker boundaries; no services."""
import errno
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

NATIVE = Path(__file__).resolve().parents[2] / 'docs/verification/HLB-433/native'
NS = 'plane-rehearsal-api-433-20261018'


@pytest.mark.parametrize('change', [
    {'DATABASE_URL':'postgresql://user:synthetic@192.168.1.129:5432/plane'},
    {'DATABASE_URL':'postgresql://user:synthetic@localhost:5432/plane'},
    {'DATABASE_URL':''},
    {'DATABASE_URL':f'postgresql://plane_fixture:synthetic@{NS}-db:bad/plane_schema_good'},
    {'DJANGO_SETTINGS_MODULE':'plane.settings.test'},
    {'DATABASE_READ_REPLICA_URL':'postgresql://user:synthetic@192.168.1.129/plane'},
])
def test_seed_rejects_nonfixture_database_before_django(tmp_path, change):
    marker=tmp_path/'django-imported'
    (tmp_path/'django.py').write_text('from pathlib import Path\n'+f'Path({str(marker)!r}).touch()\nraise RuntimeError("UNSAFE_DJANGO_IMPORT")\n')
    env={'PATH':os.environ['PATH'],'PYTHONPATH':str(tmp_path),
        'DATABASE_URL':f'postgresql://plane_fixture:synthetic@{NS}-db:5432/plane_schema_good',
        'DJANGO_SETTINGS_MODULE':'plane.settings.production',
        'REDIS_URL':f'redis://{NS}-redis:6379/0','AMQP_URL':f'redis://{NS}-redis:6379/1',**change}
    result=subprocess.run([sys.executable,str(NATIVE/'seed_schema_fixture.py')],env=env,capture_output=True,text=True,timeout=10)
    assert not marker.exists(), 'Nonfixture DB must be rejected before Django initialization'
    assert result.returncode==2
    assert result.stderr.strip()=='FIXTURE_DATABASE_DENIED'


@pytest.fixture
def fixture_scope(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('schema_fixture_under_test',NATIVE/'schema_api_fixture.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/'private-fixture';root.mkdir()
    module.ROOT=root;module.OWNED_ROOT=True
    (root/'owner').write_text(module.OWNER)
    (root/'logs').mkdir()
    (root/'pgdata').mkdir();(root/'pgdata/original-marker').write_text('synthetic original data')
    (root/'fixture.json').write_text('synthetic private credential')
    binary=tmp_path/'bin';binary.mkdir()
    docker=binary/'docker'
    docker.write_text('#!'+sys.executable+'''\nimport os,sys
if os.environ.get('DOCKER_FIXTURE_MODE')=='denied':
    print('permission denied',file=sys.stderr);sys.exit(1)
if sys.argv[2]=='inspect':sys.exit(1)
if sys.argv[2]=='ls':sys.exit(0)
raise RuntimeError('Unexpected mutation')
''');docker.chmod(0o755)
    monkeypatch.setenv('PATH',str(binary))
    return module,root


def test_inspection_failure_preserves_private_data_and_refuses_cleanup_receipt(fixture_scope,monkeypatch):
    module,root=fixture_scope
    monkeypatch.setenv('DOCKER_FIXTURE_MODE','denied')
    error=None
    try:module.cleanup()
    except RuntimeError as caught:error=str(caught)
    assert (root/'pgdata/original-marker').exists(), 'Docker inspection failure must preserve private clone'
    assert (root/'pgdata/original-marker').read_text()=='synthetic original data'
    assert error=='INSPECTION_FAILED'
    assert (root/'fixture.json').exists()
    assert not (root/'cleanup.json').exists()


def test_receipt_failure_still_cleans_owned_data_and_closes_lease(fixture_scope):
    module,root=fixture_scope
    (root/'receipts.json').mkdir()
    lease=os.open(root/'lease',os.O_CREAT|os.O_RDWR,0o600)
    with pytest.raises(OSError):
        module.finish([],lease)
    assert not (root/'pgdata').exists(), 'Receipt write failure must still clean owned clone'
    assert not (root/'fixture.json').exists()
    assert (root/'cleanup.json').exists()
    with pytest.raises(OSError) as error:os.fstat(lease)
    assert error.value.errno==errno.EBADF
