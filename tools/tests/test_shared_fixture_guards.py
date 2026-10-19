"""Shared fixture destination guards at external process boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from test_plane_restore import archive_fixture

NATIVE=Path(__file__).resolve().parents[2]/'docs/verification/HLB-434/native'
NS='plane-rehearsal-m-434-20261019'


@pytest.mark.parametrize('change',[{'AWS_S3_ENDPOINT_URL':'http://192.168.1.129:9000'},{'AWS_S3_BUCKET_NAME':'uploads'}])
def test_shared_seed_rejects_foreign_storage_before_django(tmp_path,change):
    marker=tmp_path/'django-initialized'
    (tmp_path/'socket.py').write_text(f'def gethostname():return {NS+"-cli"!r}\n')
    (tmp_path/'django.py').write_text('from pathlib import Path\n'+f'Path({str(marker)!r}).touch()\n')
    env={'PATH':os.environ['PATH'],'PYTHONPATH':str(tmp_path),
         'DATABASE_URL':'postgresql://plane_fixture:synthetic@'+NS+'-db:5432/plane_fixture_m',
         'DJANGO_SETTINGS_MODULE':'plane.settings.production','REDIS_URL':'redis://'+NS+'-redis:6379/0','AMQP_URL':'redis://'+NS+'-redis:6379/1',
         'AWS_S3_ENDPOINT_URL':'http://'+NS+'-minio:9000','AWS_S3_BUCKET_NAME':'plane-rehearsal-hlb434-m-20261019',
         'AWS_ACCESS_KEY_ID':'synthetic-fixture-access','AWS_SECRET_ACCESS_KEY':'synthetic-fixture-secret-is-private','USE_MINIO':'0','AWS_REGION':'us-east-1',**change}
    result=subprocess.run([sys.executable,str(NATIVE/'seed_shared_fixture.py')],env=env,capture_output=True,text=True,timeout=10)
    assert not marker.exists(),'Foreign asset destination must be denied before database setup'
    assert result.returncode==2 and result.stderr.strip()=='FIXTURE_ASSET_DESTINATION_DENIED'


@pytest.mark.parametrize('change',[{'endpoint':'http://192.168.1.129:9000'},{'endpoint':'http://127.0.0.1:9000'}, {'bucket':'uploads'},{'access_key':'minioadmin'}])
def test_shared_sdk_denies_foreign_store_before_client_import(tmp_path,change):
    archive,digest=archive_fixture(tmp_path)
    marker=tmp_path/'boto3-initialized'
    (tmp_path/'socket.py').write_text(f'def gethostname():return {NS+"-sdk"!r}\n')
    (tmp_path/'boto3.py').write_text('from pathlib import Path\n'+f'Path({str(marker)!r}).touch()\nraise RuntimeError("CLIENT_INITIALIZED")\n')
    connection=tmp_path/'connection.json';connection.write_text(json.dumps({'endpoint':'http://'+NS+'-minio:9000','bucket':'plane-rehearsal-hlb434-m-20261019','access_key':'synthetic-fixture-access','secret_key':'synthetic-fixture-secret-is-private',**change}));connection.chmod(0o600)
    result=subprocess.run([sys.executable,str(NATIVE/'shared_asset_sdk.py'),'ready','--connection',str(connection),'--archive',str(archive),'--expected-sha256',digest],env={'PATH':os.environ['PATH'],'PYTHONPATH':str(tmp_path)},capture_output=True,text=True,timeout=10)
    assert not marker.exists()
    assert result.returncode==2 and result.stderr.strip()=='SDK_FIXTURE_DENIED'


@pytest.mark.parametrize('name',['seed_shared_fixture.py','shared_fixture_rehearsal.py','shared_asset_sdk.py','inspect_shared_runtime.py'])
def test_shared_commands_reject_optimized_execution(name):
    result=subprocess.run([sys.executable,'-O',str(NATIVE/name)],env={'PATH':os.environ['PATH']},capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and 'OPTIMIZED_EXECUTION_DENIED' in result.stderr
