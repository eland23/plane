#!/usr/bin/env python3
"""Isolated .130 component rehearsal for the real omitted-migration API control.

Private source backup/snapshot inputs must already be staged at SOURCE. This is
not a full deployment, asset restore, readiness or release-admission command.
"""
import sys
if not __debug__:
    print('OPTIMIZED_EXECUTION_DENIED', file=sys.stderr)
    raise SystemExit(2)

import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import time
import xml.etree.ElementTree as ET

OWNER = 'HLB-433-api-schema-20261018'
NS = 'plane-rehearsal-api-433-20261018'
ROOT = Path('/var/lib/plane-release') / OWNER
SOURCE = Path('/var/lib/plane-release/HLB-434-20261018')
BACKEND = 'sha256:1c54c4fbe69d3a38740e1d05a6c0d31387050c351f0848e62c33c0a71a7c5a84'
BASE_TAG = 'plane-rehearsal-migration-e5c-backend:e5c7acf098a890436ab6300f0bc8491c7dd22725'
PG = 'sha256:468d34fefd6338031787c7b8e94078975b3aaf4d66c7ead25c39cd3ba46a15c6'
REDIS = 'sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2'
RUNNER = 'sha256:25c7d4cbb046e0929072c2197f074222e7fe9e5b1f09c75e2e3e8dc36635560f'
FAULT_TAG = NS + '-fault:missing0123'
REVISION = 'e5c7acf098a890436ab6300f0bc8491c7dd22725'
NAMES = [NS + suffix for suffix in ['-db','-redis','-api','-cli','-tests']]
NETWORK = NS + '-net'
OWNED_ROOT = False
SHELL_AUTH = 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec '
QUERY = r"""SELECT format('SELECT jsonb_build_object(''table'', %L, ''rows'', COALESCE(jsonb_agg(r ORDER BY r::text), ''[]''::jsonb))::text FROM (SELECT to_jsonb(t) AS r FROM %I.%I t) s;', tablename, schemaname, tablename) FROM pg_tables WHERE schemaname='public' ORDER BY tablename
\gexec
"""


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def inspect(kind, name):
    result = subprocess.run(['docker', kind, 'inspect', name], capture_output=True)
    if result.returncode == 0:
        try:
            rows = json.loads(result.stdout)
            require(isinstance(rows, list) and len(rows)==1 and isinstance(rows[0], dict) and isinstance(rows[0].get('Id'), str), 'INSPECTION_FAILED')
            return rows[0]
        except (ValueError, TypeError):
            raise RuntimeError('INSPECTION_FAILED') from None
    # A failed inspection alone never proves absence. Confirm through a
    # successful structured listing; daemon/permission/transport errors block.
    listing = subprocess.run(['docker', kind, 'ls', *(['-a'] if kind=='container' else []),
        '--no-trunc', '--format', '{{json .}}'], capture_output=True)
    require(listing.returncode==0, 'INSPECTION_FAILED')
    try:
        rows = [json.loads(line) for line in listing.stdout.splitlines()]
        names = set()
        for row in rows:
            if kind=='image':
                require(all(isinstance(row.get(k),str) for k in ('ID','Repository','Tag')), 'INSPECTION_FAILED')
                names.update([row['ID'],row['Repository']+':'+row['Tag']])
            else:
                key = 'Names' if kind=='container' else 'Name'
                require(isinstance(row.get(key),str), 'INSPECTION_FAILED')
                names.add(row[key])
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError('INSPECTION_FAILED') from None
    require(name not in names, 'INSPECTION_FAILED')
    return None


def run(argv, data=None, timeout=240, accepted=(0,)):
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(data, timeout=timeout)
    finally:
        try:os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait()
    log = ROOT / 'logs' / (secrets.token_hex(8) + '.log')
    with log.open('xb') as output:
        log.chmod(0o600)
        output.write(stdout + stderr)
    require(process.returncode in accepted, 'FIXTURE_COMMAND_FAILED')
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def private_file(path, content):
    with path.open('xb') as stream:
        path.chmod(0o600)
        stream.write(content)


def owned_container(name):
    info = inspect('container', name)
    if info:
        require(info['Config']['Labels'].get('io.plane.rehearsal.owner') == OWNER, 'FOREIGN_CONTAINER_DENIED')
    return info


def remove_container(name):
    if owned_container(name):
        run(['docker','rm','-f','-v',name])
        require(inspect('container',name) is None, 'CONTAINER_CLEANUP_FAILED')


def pg(tool, database, extra=(), data=None):
    shell = SHELL_AUTH + tool + ' -w -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER"'
    shell += (' -d ' if tool != 'createdb' else ' ') + database
    shell += ' ' + ' '.join(extra)
    return run(['docker','exec','-i','-e','PGOPTIONS=-c timezone=UTC',NS+'-db','sh','-c',shell],data=data)


def app_cli(code=None, args=None, bad=False):
    env = ROOT / ('bad.env' if bad else 'app.env')
    command = ['docker','run','--rm','--name',NS+'-cli','--label','io.plane.rehearsal.owner='+OWNER,
        '--hostname',NS+'-cli','--network',NETWORK,'--memory','384m','--memory-swap','384m','--cpus','1','--pids-limit','128',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=32m','--tmpfs','/code/plane/logs:rw,nosuid,size=16m',
        '--env-file',str(env),BACKEND]
    if code is not None:
        command.insert(command.index(BACKEND),'-i')
        command += ['python','-']
        return run(command,data=code.encode())
    return run(command + ['python','manage.py',*args])


def baseline(preserve_only=False):
    current = pg('psql','plane_schema_good',('-X','-A','-t','--set','ON_ERROR_STOP=1'),QUERY.encode()).stdout
    original = (SOURCE/'source.logical-snapshot.v2.jsonl').read_bytes()
    expected = {r['table']:r['rows'] for r in map(json.loads,original.splitlines())}
    actual = {r['table']:r['rows'] for r in map(json.loads,current.splitlines())}
    if not preserve_only:
        require(actual == expected, 'ORIGINAL_RESTORE_EQUALITY_FAILED')
    else:
        for table, rows in expected.items():
            require(table in actual, 'ORIGINAL_TABLE_LOST')
            for row in rows:
                require(any(all(candidate.get(k)==v for k,v in row.items()) for candidate in actual[table]), 'ORIGINAL_RECORD_CHANGED')
    return {'tables':len(expected),'original_rows':sum(map(len,expected.values())),'exact_before_migration':not preserve_only,'original_values_preserved':True}


def start_api(bad=False):
    remove_container(NS+'-api')
    image = inspect('image',FAULT_TAG)['Id'] if bad else BACKEND
    run(['docker','run','-d','--name',NS+'-api','--label','io.plane.rehearsal.owner='+OWNER,
        '--network',NETWORK,'--memory','384m','--memory-swap','384m','--cpus','1','--pids-limit','128',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=32m','--tmpfs','/code/plane/logs:rw,nosuid,size=16m',
        '--env-file',str(ROOT/('bad.env' if bad else 'app.env')),image,
        'gunicorn','--bind','0.0.0.0:8000','--workers','1','--timeout','180','plane.wsgi:application'])
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        response=run(['docker','exec',NS+'-api','python','-c',
            'from urllib.request import urlopen; print(urlopen("http://127.0.0.1:8000/api/instances/",timeout=5).status)'],
            timeout=15,accepted=(0,1))
        if response.returncode==0 and response.stdout.strip()==b'200':return
        time.sleep(2)
    raise RuntimeError('API_BOOTSTRAP_FAILED')


def test_phase(name, fault=False):
    args=['docker','run','--rm','--name',NS+'-tests','--label','io.plane.rehearsal.owner='+OWNER,
        '--network',NETWORK,'--memory','128m','--memory-swap','128m','--cpus','1','--pids-limit','64',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=16m','-e','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
        '-e','PYTHONDONTWRITEBYTECODE=1','-e','PLANE_SCHEMA_FIXTURE=/private/fixture.json',
        '-v',str(ROOT/'testsrc')+':/tests:ro','-v',str(ROOT/'fixture.json')+':/private/fixture.json:ro',
        '-v',str(ROOT/'evidence')+':/evidence',RUNNER,'python','-m','pytest','/tests/test_schema_api.py',
        '-q','-o','addopts=','-p','no:cacheprovider','--junitxml=/evidence/'+name+'.xml']
    if fault:args+=['-k','complete_packaged_schema']
    result=run(args,accepted=(1,) if fault else (0,))
    private_file(ROOT/'evidence'/(name+'.log'),result.stdout+result.stderr)
    tree=ET.parse(ROOT/'evidence'/(name+'.xml'))
    suites=list(tree.getroot().iter('testsuite'))
    require(sum(int(s.get('errors','0')) for s in suites)==0,'API_TEST_SETUP_ERROR')
    require(sum(int(s.get('failures','0')) for s in suites)==(1 if fault else 0),'WRONG_API_TEST_RESULT')
    require(sum(int(s.get('tests','0')) for s in suites)==(1 if fault else 2),'API_TEST_COUNT_CHANGED')
    if fault:
        require('Complete packaged schema must serve issue-link API' in (ROOT/'evidence'/(name+'.log')).read_text(),'WRONG_FAULT_ASSERTION')
    return {'phase':name,'exit':result.returncode,'intended_schema_failure':fault}


def verify_runner():
    result=run(['docker','run','--rm','--name',NS+'-tests','--label','io.plane.rehearsal.owner='+OWNER,
        '--network','none','--memory','128m','--memory-swap','128m','--cpus','1','--pids-limit','64',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=16m',RUNNER,'python','-m','pytest','--version'])
    require(result.stdout.strip()==b'pytest 9.0.3','TEST_RUNNER_REQUIRED')


def prepare():
    global OWNED_ROOT
    require(not ROOT.exists() and ROOT.resolve()==ROOT,'FIXTURE_OUTPUT_EXISTS_OR_SYMLINK')
    for name in NAMES:require(inspect('container',name) is None,'EXISTING_CONTAINER_DENIED')
    require(inspect('network',NETWORK) is None and inspect('image',FAULT_TAG) is None,'EXISTING_RESOURCE_DENIED')
    for filename,digest in [('source.database.v2.dump','0cf879ce0cff92ada369167e9d6c3fd38d08fbfae67d3d4f1e24099ec2134849'),('source.logical-snapshot.v2.jsonl','951160d6a4523255cb295828c8b833c402f518fff8ec945b30b6cf541dbd7848')]:
        p=SOURCE/filename
        require(p.is_file() and not p.is_symlink() and p.stat().st_mode&0o777==0o600,'PRIVATE_BACKUP_REQUIRED')
        require(hashlib.sha256(p.read_bytes()).hexdigest()==digest,'SOURCE_BACKUP_MISMATCH')
    memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    require(int(memory['MemAvailable'].split()[0])>=960*1024,'COMPONENT_MEMORY_RESERVATION')
    require(shutil.disk_usage('/var/lib/docker').free>=2*1024**3,'COMPONENT_DISK_RESERVATION')
    for image in [BACKEND,PG,REDIS,RUNNER]:require(inspect('image',image) is not None,'PINNED_IMAGE_REQUIRED')
    info=inspect('image',BACKEND)
    keys=('Env','Cmd','Entrypoint','WorkingDir','User','Labels','ExposedPorts','Volumes','Healthcheck','Shell','StopSignal')
    payload={'rootfs':info['RootFS'],'config':{key:info['Config'].get(key) for key in keys}}
    require(hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()=='8e7ddf80e918f7a1360a43aeb0cbc68902ef33878ce2215b7bd6135e61ba94cc','BACKEND_PAYLOAD_MISMATCH')
    require(info['Config']['Labels']['org.opencontainers.image.revision']==REVISION,'WRONG_APPLICATION_REVISION')
    ROOT.mkdir(mode=0o700)
    private_file(ROOT/'owner',OWNER.encode())
    OWNED_ROOT = True
    for name in ['logs','evidence','testsrc','pgdata','fault-build']:(ROOT/name).mkdir(mode=0o700)
    verify_runner()
    shutil.copyfile(Path(__file__).with_name('test_schema_api.py'),ROOT/'testsrc/test_schema_api.py')
    password=secrets.token_urlsafe(32)
    private_file(ROOT/'db.env',f'POSTGRES_USER=plane_fixture\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=plane_schema_good\n'.encode())
    env=f'DJANGO_SETTINGS_MODULE=plane.settings.production\nSECRET_KEY={secrets.token_urlsafe(48)}\nDATABASE_URL=postgresql://plane_fixture:{password}@{NS}-db:5432/plane_schema_good\nREDIS_URL=redis://{NS}-redis:6379/0\nAMQP_URL=redis://{NS}-redis:6379/1\nWEB_URL=http://127.0.0.1:18191\nALLOWED_HOSTS=127.0.0.1,{NS}-api\nDEBUG=0\nSCOUT_MONITOR=\n'
    private_file(ROOT/'app.env',env.encode())
    private_file(ROOT/'bad.env',env.replace('/plane_schema_good','/plane_schema_bad').encode())
    run(['docker','network','create','--internal','--label','io.plane.rehearsal.owner='+OWNER,NETWORK])
    run(['docker','run','-d','--name',NS+'-db','--label','io.plane.rehearsal.owner='+OWNER,'--network',NETWORK,
        '--memory','256m','--memory-swap','256m','--cpus','1','--pids-limit','128','--read-only',
        '--tmpfs','/tmp:rw,nosuid,size=32m','--tmpfs','/var/run/postgresql:rw,nosuid,size=8m',
        '-v',str(ROOT/'pgdata')+':/var/lib/postgresql/data','--env-file',str(ROOT/'db.env'),PG])
    run(['docker','run','-d','--name',NS+'-redis','--label','io.plane.rehearsal.owner='+OWNER,'--network',NETWORK,
        '--memory','64m','--memory-swap','64m','--cpus','0.25','--pids-limit','64','--read-only','--tmpfs','/data:rw,nosuid,size=32m',
        REDIS,'redis-server','--save','','--appendonly','no'])
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        r=subprocess.run(['docker','exec',NS+'-db','pg_isready','-h','127.0.0.1','-U','plane_fixture'],capture_output=True)
        if r.returncode==0:break
        time.sleep(2)
    else:raise RuntimeError('DATABASE_BOOTSTRAP_FAILED')
    pg('pg_restore','plane_schema_good',('--clean','--if-exists','--no-owner','--no-acl','--exit-on-error'),(SOURCE/'source.database.v2.dump').read_bytes())


def cleanup():
    if not ROOT.exists():return
    require((ROOT/'owner').read_text()==OWNER,'FOREIGN_ROOT_DENIED')
    for name in reversed(NAMES):remove_container(name)
    net=inspect('network',NETWORK)
    if net:
        require(net['Labels'].get('io.plane.rehearsal.owner')==OWNER and not net['Containers'],'FOREIGN_NETWORK_DENIED')
        run(['docker','network','rm',NETWORK])
    fault=inspect('image',FAULT_TAG)
    if fault:
        require(fault['Config']['Labels'].get('io.plane.rehearsal.owner')==OWNER,'FOREIGN_IMAGE_DENIED')
        run(['docker','image','rm',fault['Id']])
    if (ROOT/'pgdata').exists():shutil.rmtree(ROOT/'pgdata')
    for name in ['app.env','bad.env','db.env','fixture.json','good-fixture.dump']:
        (ROOT/name).unlink(missing_ok=True)
    private_file(ROOT/'cleanup.json',json.dumps({'containers_remaining':0,'network_removed':True,'fault_image_removed':True,'cloned_database_and_fixture_credentials_removed':True}).encode())


def finish(receipts, lease):
    try:
        if OWNED_ROOT:
            try:
                private_file(ROOT/'receipts.json',json.dumps(receipts,indent=2).encode())
            finally:
                cleanup()
    finally:
        os.close(lease)


def main():
    require(socket.gethostname()=='fashionfindrs-dev','VM_ONLY')
    addresses=json.loads(subprocess.check_output(['ip','-j','address']))
    require(any(a.get('local')=='192.168.1.130' for item in addresses for a in item.get('addr_info',[])),'TARGET_DENIED')
    lease=os.open('/var/lock/plane-rehearsal-runtime.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    receipts=[]
    try:
        prepare()
        restored=baseline()
        private_file(ROOT/'restore-integrity.json',json.dumps(restored).encode())
        app_cli(args=['migrate','--noinput'])
        seed=Path(__file__).with_name('seed_schema_fixture.py').read_text()
        private_file(ROOT/'fixture.json',app_cli(code=seed).stdout)
        start_api()
        receipts.append(test_phase('pass-known-state'))
        remove_container(NS+'-api')
        private_file(ROOT/'good-fixture.dump',pg('pg_dump','plane_schema_good',('--format=custom','--no-owner','--no-acl')).stdout)
        pg('createdb','plane_schema_bad')
        pg('pg_restore','plane_schema_bad',('--clean','--if-exists','--no-owner','--no-acl','--exit-on-error'),(ROOT/'good-fixture.dump').read_bytes())
        app_cli(args=['migrate','db','0122','--noinput'],bad=True)
        require(inspect('image',BASE_TAG)['Id']==BACKEND,'BASE_TAG_CHANGED')
        private_file(ROOT/'fault-build/Dockerfile',('FROM '+BASE_TAG+'\nRUN rm /code/plane/db/migrations/0123_issue_link_source_identity.py /code/plane/db/migrations/0124_module_milestones.py\n').encode())
        run(['docker','build','--pull=false','--label','io.plane.rehearsal.owner='+OWNER,'-t',FAULT_TAG,str(ROOT/'fault-build')])
        require(inspect('image',BASE_TAG)['Id']==BACKEND,'BASE_TAG_CHANGED')
        fault=inspect('image',FAULT_TAG)
        require(fault['RootFS']['Layers'][:len(inspect('image',BACKEND)['RootFS']['Layers'])]==inspect('image',BACKEND)['RootFS']['Layers'],'FAULT_BASE_CHANGED')
        private_file(ROOT/'fault-identity.json',json.dumps({'image':fault['Id'],'omitted':['0123_issue_link_source_identity.py','0124_module_milestones.py'],'database_leaf':'0122','application_revision':REVISION}).encode())
        start_api(bad=True)
        receipts.append(test_phase('failure-omitted-migration',fault=True))
        start_api()
        receipts.append(test_phase('restore-and-repeat'))
        private_file(ROOT/'preservation.json',json.dumps(baseline(preserve_only=True)).encode())
    finally:
        finish(receipts, lease)
    print(json.dumps({'result':'PASS','phases':receipts,'runtime_release_admitted':False}))


if __name__=='__main__':main()
