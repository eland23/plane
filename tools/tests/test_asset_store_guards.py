"""Native guards at process/file/Docker boundaries; no hosted services."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from test_plane_restore import archive_fixture

NATIVE=Path(__file__).resolve().parents[2]/'docs/verification/HLB-434/native'
NS='plane-rehearsal-434-assets-20261018'


@pytest.mark.parametrize('change',[
    {'endpoint':'http://192.168.1.129:9000'},
    {'endpoint':'http://127.0.0.1:9000'},
    {'bucket':'uploads'},
    {'access_key':'minioadmin'},
    {'secret_key':''},
    {'unexpected':'extra-configuration'},
])
def test_sdk_rejects_foreign_connection_before_loading_s3_client(tmp_path,change):
    archive,digest=archive_fixture(tmp_path)
    marker=tmp_path/'client-initialized'
    (tmp_path/'socket.py').write_text(f'def gethostname():return {NS+"-sdk"!r}\n')
    (tmp_path/'boto3.py').write_text('from pathlib import Path\n'+f'Path({str(marker)!r}).touch()\nraise RuntimeError("UNSAFE_CLIENT_IMPORT")\n')
    connection=tmp_path/'connection.json'
    config={'endpoint':'http://'+NS+'-minio:9000','bucket':'plane-rehearsal-hlb434-assets-20261018',
            'access_key':'fixture-access-key','secret_key':'fixture-secret-key-is-private-only',**change}
    connection.write_text(json.dumps(config));connection.chmod(0o600)
    result=subprocess.run([sys.executable,str(NATIVE/'asset_store_sdk.py'),'ready','--connection',str(connection),
                           '--archive',str(archive),'--expected-sha256',digest],
                          env={'PATH':os.environ['PATH'],'PYTHONPATH':str(tmp_path)},capture_output=True,text=True,timeout=10)
    assert not marker.exists(),'Foreign connection must be denied before S3 client initialization'
    assert result.returncode==2
    assert result.stderr.strip()=='SDK_FIXTURE_DENIED'


@pytest.mark.parametrize('name',['asset_store_rehearsal.py','asset_store_sdk.py'])
@pytest.mark.parametrize('mode',['flag','environment'])
def test_native_commands_deny_optimized_execution_before_operations(tmp_path,name,mode):
    env={'PATH':os.environ['PATH']}
    args=[sys.executable]
    if mode=='flag':args+=['-O']
    else:env['PYTHONOPTIMIZE']='1'
    result=subprocess.run([*args,str(NATIVE/name)],env=env,capture_output=True,text=True,timeout=10)
    assert result.returncode==2
    assert result.stderr.strip()=='OPTIMIZED_EXECUTION_DENIED'


@pytest.fixture
def cleanup_scope(tmp_path,monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('asset_rehearsal_under_test',NATIVE/'asset_store_rehearsal.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/'private';root.mkdir()
    module.ROOT=root;module.OWNED=True
    (root/'owner').write_text(module.OWNER)
    (root/'logs').mkdir();(root/'readbacks').mkdir()
    (root/'readbacks/original-marker').write_text('synthetic readback')
    (root/'connection.json').write_text('synthetic private credential')
    (root/'minio.env').write_text('synthetic private environment')
    archive,digest=archive_fixture(tmp_path);module.SOURCE=archive;module.ARCHIVE_SHA=digest
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


def test_indeterminate_docker_state_preserves_data_and_refuses_clean_receipt(cleanup_scope,monkeypatch):
    module,root=cleanup_scope
    monkeypatch.setenv('DOCKER_FIXTURE_MODE','denied')
    error=None
    try:module.cleanup()
    except RuntimeError as caught:error=str(caught)
    assert (root/'readbacks/original-marker').exists(),'Indeterminate Docker state must preserve readbacks'
    assert error=='INSPECTION_FAILED'
    assert (root/'connection.json').exists()
    assert not (root/'cleanup.json').exists()


def test_receipt_failure_still_removes_readbacks_credentials_and_releases_lease(cleanup_scope):
    import errno
    module,root=cleanup_scope
    (root/'receipts.json').mkdir()
    lease=os.open(root/'lease',os.O_CREAT|os.O_RDWR,0o600)
    with pytest.raises(OSError):module.finish([],lease)
    assert not (root/'readbacks').exists(),'Receipt failure must still remove owned readbacks'
    assert not (root/'connection.json').exists()
    assert not (root/'minio.env').exists()
    assert (root/'cleanup.json').exists()
    with pytest.raises(OSError) as error:os.fstat(lease)
    assert error.value.errno==errno.EBADF
