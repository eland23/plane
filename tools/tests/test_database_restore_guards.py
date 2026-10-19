"""Database rehearsal guards at process boundaries, without hosted services."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

NATIVE=Path(__file__).resolve().parents[2]/'docs/verification/HLB-434/native'


@pytest.mark.parametrize('url',[
    'postgresql://plane_fixture:synthetic@192.168.1.129:5432/plane_restore_good',
    'postgresql://plane_fixture:synthetic@127.0.0.1:5432/plane_restore_good',
    'postgresql://plane_fixture:synthetic@plane-rehearsal-db-434-20261019-db:5432/postgres',
    'postgresql://postgres:synthetic@plane-rehearsal-db-434-20261019-db:5432/plane_restore_good',
    'postgresql://plane_fixture:synthetic@plane-rehearsal-db-434-20261019-db:5432/plane_restore_good?options=unsafe',
])
def test_database_seed_denies_foreign_destination_before_django_import(tmp_path,url):
    ns='plane-rehearsal-db-434-20261019'
    (tmp_path/'socket.py').write_text(f'def gethostname():return {ns+"-cli"!r}\n')
    marker=tmp_path/'django-imported'
    (tmp_path/'django.py').write_text('from pathlib import Path\n'+f'Path({str(marker)!r}).touch()\n')
    result=subprocess.run([sys.executable,str(NATIVE/'seed_database_fixture.py')],
        env={'PATH':os.environ['PATH'],'PYTHONPATH':str(tmp_path),'DATABASE_URL':url,
             'DJANGO_SETTINGS_MODULE':'plane.settings.production',
             'REDIS_URL':'redis://'+ns+'-redis:6379/0','AMQP_URL':'redis://'+ns+'-redis:6379/1'},
        capture_output=True,text=True,timeout=10)
    assert not marker.exists(),'Foreign database must be rejected before Django initializes'
    assert result.returncode==2
    assert result.stderr.strip()=='FIXTURE_DATABASE_DENIED'


@pytest.mark.parametrize('name',['database_restore_rehearsal.py','seed_database_fixture.py'])
def test_database_commands_deny_optimized_execution(tmp_path,name):
    result=subprocess.run([sys.executable,'-O',str(NATIVE/name)],env={'PATH':os.environ['PATH']},
        capture_output=True,text=True,timeout=10)
    assert result.returncode==2
    assert result.stderr.strip()=='OPTIMIZED_EXECUTION_DENIED'
