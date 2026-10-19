#!/usr/bin/env python3
"""Isolated .130 database restore and real API record-integrity control.

Private source backup/snapshot inputs must already be staged at SOURCE. This is
not a full deployment, asset restore, readiness or release-admission command.
"""
import sys
if not __debug__:
    print('OPTIMIZED_EXECUTION_DENIED',file=sys.stderr)
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

OWNER = 'HLB-434-shared-m-20261019'
NS = 'plane-rehearsal-m-434-20261019'
ROOT = Path('/var/lib/plane-release') / OWNER
SOURCE = Path('/var/lib/plane-release/HLB-434-20261018')
SOURCE_TREE=Path(__file__).resolve().parents[4]
ASSET_SHA='df778660d7564f29eded43f1db31cdbda686e4f5526ef6df7f0143635e14547f'
MINIO='sha256:30cfd6ed962109b44a4bf2122e0b64c172feaf5453f9eb30888eda03585ee50f'
INPUTS={'source.assets.tar':ASSET_SHA,'source.database.v2.dump':'0cf879ce0cff92ada369167e9d6c3fd38d08fbfae67d3d4f1e24099ec2134849','source.logical-snapshot.v2.jsonl':'951160d6a4523255cb295828c8b833c402f518fff8ec945b30b6cf541dbd7848'}
BACKEND = 'sha256:1c54c4fbe69d3a38740e1d05a6c0d31387050c351f0848e62c33c0a71a7c5a84'
PG = 'sha256:468d34fefd6338031787c7b8e94078975b3aaf4d66c7ead25c39cd3ba46a15c6'
REDIS = 'sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2'
RUNNER = 'sha256:25c7d4cbb046e0929072c2197f074222e7fe9e5b1f09c75e2e3e8dc36635560f'
REVISION = 'e5c7acf098a890436ab6300f0bc8491c7dd22725'
NAMES = [NS + suffix for suffix in ['-db','-redis','-minio','-api','-cli','-sdk','-tests']]
NETWORK = NS + '-net'
OWNED_ROOT = False
SHELL_AUTH = 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec '
QUERY = r"""BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT format('SELECT jsonb_build_object(''table'', %L, ''rows'', COALESCE(jsonb_agg(r ORDER BY r::text), ''[]''::jsonb))::text FROM (SELECT to_jsonb(t) AS r FROM %I.%I t) s;', tablename, schemaname, tablename) FROM pg_tables WHERE schemaname='public' ORDER BY tablename
\gexec
COMMIT;
"""


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def inspect(kind, name):
    result = subprocess.run(['docker', kind, 'inspect', name], capture_output=True,timeout=30)
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
        '--no-trunc', '--format', '{{json .}}'], capture_output=True,timeout=30)
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


DIAGNOSTIC_FAILURES=[]

def run(argv, data=None, timeout=240, accepted=(0,), log_required=True):
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(data, timeout=timeout)
    finally:
        try:os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait()
    try:private_file(ROOT/'logs'/(secrets.token_hex(8)+'.log'),stdout+stderr)
    except OSError:
        if log_required:raise
        DIAGNOSTIC_FAILURES.append('DIAGNOSTIC_WRITE_FAILED')
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
        run(['docker','rm','-f','-v',name],log_required=False)
        require(inspect('container',name) is None, 'CONTAINER_CLEANUP_FAILED')


def pg(tool, database, extra=(), data=None):
    shell = SHELL_AUTH + tool + ' -w -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER"'
    shell += (' -d ' if tool != 'createdb' else ' ') + database
    shell += ' ' + ' '.join(extra)
    return run(['docker','exec','-i','-e','PGOPTIONS=-c timezone=UTC',NS+'-db','sh','-c',shell],data=data)


def app_cli(code=None, args=None):
    env = ROOT/'app.env'
    command = ['docker','run','--rm','--name',NS+'-cli','--label','io.plane.rehearsal.owner='+OWNER,
        '--hostname',NS+'-cli','--network',NETWORK,'--memory','384m','--memory-swap','384m','--cpus','1','--pids-limit','128',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=32m','--tmpfs','/code/plane/logs:rw,nosuid,size=16m',
        '--env-file',str(env),'-v',str(SOURCE_TREE/'docs/verification/HLB-434/native')+':/fixtures:ro',BACKEND]
    if code is not None:
        command.insert(command.index(BACKEND),'-i')
        command += ['python','-']
        return run(command,data=code.encode())
    return run(command + ['python','manage.py',*args])


def baseline(name,preserve_only=False):
    current=pg('psql','plane_fixture_m',('-X','-q','-A','-t','--set','ON_ERROR_STOP=1'),QUERY.encode()).stdout
    target=ROOT/'readbacks'/(name+'.jsonl');private_file(target,current)
    args=[sys.executable,str(SOURCE_TREE/'tools/plane_restore.py'),'compare-database',
          '--expected',str(SOURCE/'source.logical-snapshot.v2.jsonl'),'--actual',str(target),
          '--expected-sha256','951160d6a4523255cb295828c8b833c402f518fff8ec945b30b6cf541dbd7848']
    if preserve_only:args+=['--allow-additions']
    return json.loads(run(args).stdout)


def start_api():
    remove_container(NS+'-api')
    image = BACKEND
    run(['docker','run','-d','--name',NS+'-api','--label','io.plane.rehearsal.owner='+OWNER,
        '--network',NETWORK,'--memory','384m','--memory-swap','384m','--cpus','1','--pids-limit','128',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=32m','--tmpfs','/code/plane/logs:rw,nosuid,size=16m',
        '--env-file',str(ROOT/'app.env'),image,
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
    readback=ROOT/'readbacks'/name;readback.mkdir(mode=0o700)
    sdk('snapshot',readback)
    args=['docker','run','--rm','--name',NS+'-tests','--label','io.plane.rehearsal.owner='+OWNER,
        '--network',NETWORK,'--memory','128m','--memory-swap','128m','--cpus','1','--pids-limit','64',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=16m','-e','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
        '-e','PYTHONDONTWRITEBYTECODE=1','-e','PLANE_RESTORE_FIXTURE=/private/fixture.json',
        '-v',str(ROOT/'testsrc')+':/tests:ro','-v',str(ROOT/'fixture.json')+':/private/fixture.json:ro',
        '-v',str(readback)+':/readback:ro','-v',str(SOURCE/'source.assets.tar')+':/original/source.assets.tar:ro',
        '-v',str(SOURCE_TREE/'tools')+':/workspace/tools:ro','-v',str(ROOT/'evidence')+':/evidence',RUNNER,'python','-m','pytest','/tests/test_shared_fixture_m.py','/tests/test_asset_store.py',
        '-q','-o','addopts=','-p','no:cacheprovider','--junitxml=/evidence/'+name+'.xml']
    result=run(args,accepted=(1,) if fault else (0,))
    private_file(ROOT/'evidence'/(name+'.log'),result.stdout+result.stderr)
    tree=ET.parse(ROOT/'evidence'/(name+'.xml'))
    suites=list(tree.getroot().iter('testsuite'))
    require(sum(int(s.get('errors','0')) for s in suites)==0,'API_TEST_SETUP_ERROR')
    require(sum(int(s.get('failures','0')) for s in suites)==(2 if fault else 0),'WRONG_API_TEST_RESULT')
    require(sum(int(s.get('tests','0')) for s in suites)==28,'API_TEST_COUNT_CHANGED')
    require(sum(int(s.get('skipped','0')) for s in suites)==0,'API_TEST_SKIPPED')
    if fault:
        failures=[case.get('name') for case in tree.getroot().iter('testcase') if case.find('failure') is not None]
        require(sorted(failures)==sorted(['test_associated_assets_download_through_authenticated_api_and_match_golden_bytes[binary-1]','test_restored_asset_bytes_match_original_and_golden_hashes']),'WRONG_FAULT_CASES')
        require('Associated fixture asset bytes must match golden SHA-256' in (ROOT/'evidence'/(name+'.log')).read_text(),'WRONG_FAULT_ASSERTION')
    return {'phase':name,'exit':result.returncode,'intended_asset_corruption_failure':fault}


def verify_runner():
    result=run(['docker','run','--rm','--name',NS+'-tests','--label','io.plane.rehearsal.owner='+OWNER,
        '--network','none','--memory','128m','--memory-swap','128m','--cpus','1','--pids-limit','64',
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=16m',RUNNER,'python','-m','pytest','--version'])
    require(result.stdout.strip()==b'pytest 9.0.3','TEST_RUNNER_REQUIRED')


def sdk(action,readback=None,accepted=(0,)):
    return run(['docker','run','--rm','--name',NS+'-sdk','--hostname',NS+'-sdk',
        '--label','io.plane.rehearsal.owner='+OWNER,'--network',NETWORK,'--memory','256m','--memory-swap','256m',
        '--cpus','1','--pids-limit','64','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--tmpfs','/tmp:rw,nosuid,noexec,size=32m','-e','PYTHONDONTWRITEBYTECODE=1',
        '-v',str(SOURCE_TREE)+':/workspace:ro','-v',str(SOURCE/'source.assets.tar')+':/original/source.assets.tar:ro',
        '-v',str(ROOT/'connection.json')+':/private/connection.json:ro','-v',str(readback or ROOT/'scratch')+':/readback',
        '--entrypoint','python',BACKEND,'/workspace/docs/verification/HLB-434/native/shared_asset_sdk.py',action,
        '--connection','/private/connection.json','--archive','/original/source.assets.tar','--expected-sha256',ASSET_SHA],accepted=accepted)


def start_store():
    run(['docker','run','-d','--name',NS+'-minio','--label','io.plane.rehearsal.owner='+OWNER,'--network',NETWORK,
        '--memory','256m','--memory-swap','256m','--cpus','1','--pids-limit','128','--user','1000:1000',
        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--tmpfs','/tmp:rw,nosuid,noexec,size=32m','--tmpfs','/data:rw,nosuid,noexec,size=1g,uid=1000,gid=1000,mode=0700',
        '--env-file',str(ROOT/'minio.env'),'--entrypoint','minio',MINIO,'server','--address',':9000','--quiet','/data'])
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        if sdk('ready',accepted=(0,1)).returncode==0:return
        time.sleep(2)
    raise RuntimeError('OBJECT_STORE_BOOTSTRAP_FAILED')


def prepare():
    global OWNED_ROOT
    require(not ROOT.exists() and ROOT.resolve()==ROOT,'FIXTURE_OUTPUT_EXISTS_OR_SYMLINK')
    for name in NAMES:require(inspect('container',name) is None,'EXISTING_CONTAINER_DENIED')
    require(inspect('network',NETWORK) is None,'EXISTING_RESOURCE_DENIED')
    for filename,digest in INPUTS.items():
        p=SOURCE/filename
        require(p.is_file() and not p.is_symlink() and p.stat().st_mode&0o777==0o600 and p.stat().st_size<=64*1024**2,'PRIVATE_BACKUP_REQUIRED')
        require(hashlib.sha256(p.read_bytes()).hexdigest()==digest,'SOURCE_BACKUP_MISMATCH')
    memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    require(int(memory['MemAvailable'].split()[0])>=1536*1024,'COMPONENT_MEMORY_RESERVATION')
    require(shutil.disk_usage('/var/lib/docker').free>=2*1024**3,'COMPONENT_DISK_RESERVATION')
    for image in [BACKEND,PG,REDIS,RUNNER,MINIO]:require(inspect('image',image) is not None,'PINNED_IMAGE_REQUIRED')
    info=inspect('image',BACKEND)
    keys=('Env','Cmd','Entrypoint','WorkingDir','User','Labels','ExposedPorts','Volumes','Healthcheck','Shell','StopSignal')
    payload={'rootfs':info['RootFS'],'config':{key:info['Config'].get(key) for key in keys}}
    require(hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()=='8e7ddf80e918f7a1360a43aeb0cbc68902ef33878ce2215b7bd6135e61ba94cc','BACKEND_PAYLOAD_MISMATCH')
    require(info['Config']['Labels']['org.opencontainers.image.revision']==REVISION,'WRONG_APPLICATION_REVISION')
    ROOT.mkdir(mode=0o700)
    private_file(ROOT/'owner',OWNER.encode())
    OWNED_ROOT = True
    for name in ['logs','evidence','testsrc','pgdata','readbacks','scratch']:(ROOT/name).mkdir(mode=0o700)
    verify_runner()
    for name in ['test_shared_fixture_m.py','test_asset_store.py','shared_fixture_m.json','asset_fixture.py']:
        shutil.copyfile(Path(__file__).with_name(name),ROOT/'testsrc'/name)
    password=secrets.token_urlsafe(32)
    private_file(ROOT/'db.env',f'POSTGRES_USER=plane_fixture\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=plane_fixture_m\n'.encode())
    env=f'DJANGO_SETTINGS_MODULE=plane.settings.production\nSECRET_KEY={secrets.token_urlsafe(48)}\nDATABASE_URL=postgresql://plane_fixture:{password}@{NS}-db:5432/plane_fixture_m\nREDIS_URL=redis://{NS}-redis:6379/0\nAMQP_URL=redis://{NS}-redis:6379/1\nWEB_URL=http://127.0.0.1:18191\nALLOWED_HOSTS=127.0.0.1,{NS}-api\nDEBUG=0\nSCOUT_MONITOR=\n'
    access='plane'+secrets.token_hex(8);secret=secrets.token_urlsafe(32)
    env+=f'USE_MINIO=0\nAWS_EC2_METADATA_DISABLED=true\nAWS_ACCESS_KEY_ID={access}\nAWS_SECRET_ACCESS_KEY={secret}\nAWS_S3_BUCKET_NAME=plane-rehearsal-hlb434-m-20261019\nAWS_REGION=us-east-1\nAWS_S3_ENDPOINT_URL=http://{NS}-minio:9000\n'
    private_file(ROOT/'app.env',env.encode())
    private_file(ROOT/'minio.env',f'MINIO_ROOT_USER={access}\nMINIO_ROOT_PASSWORD={secret}\nMINIO_BROWSER=off\nHOME=/tmp\n'.encode())
    private_file(ROOT/'connection.json',json.dumps({'endpoint':'http://'+NS+'-minio:9000','bucket':'plane-rehearsal-hlb434-m-20261019','access_key':access,'secret_key':secret}).encode())
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
        r=subprocess.run(['docker','exec',NS+'-db','pg_isready','-h','127.0.0.1','-U','plane_fixture'],capture_output=True,timeout=30)
        if r.returncode==0:break
        time.sleep(2)
    else:raise RuntimeError('DATABASE_BOOTSTRAP_FAILED')
    pg('pg_restore','plane_fixture_m',('--clean','--if-exists','--no-owner','--no-acl','--exit-on-error'),(SOURCE/'source.database.v2.dump').read_bytes())


def cleanup():
    require((ROOT/'owner').read_text()==OWNER,'FOREIGN_ROOT_DENIED')
    for name in reversed(NAMES):remove_container(name)
    net=inspect('network',NETWORK)
    if net:
        require(net['Labels'].get('io.plane.rehearsal.owner')==OWNER and not net['Containers'],'FOREIGN_NETWORK_DENIED')
        run(['docker','network','rm',NETWORK],log_required=False)
        require(inspect('network',NETWORK) is None,'NETWORK_CLEANUP_FAILED')
    for name in ['pgdata','readbacks','scratch']:
        if (ROOT/name).exists():shutil.rmtree(ROOT/name)
    for name in ['app.env','db.env','minio.env','connection.json','fixture.json','good-fixture.dump']:(ROOT/name).unlink(missing_ok=True)
    for filename,digest in INPUTS.items():
        require(hashlib.sha256((SOURCE/filename).read_bytes()).hexdigest()==digest,'ORIGINAL_BACKUP_CHANGED')
    private_file(ROOT/'cleanup.json',json.dumps({'containers_remaining':0,'network_removed':True,
        'restored_database_readbacks_and_credentials_removed':True,'original_backups_preserved':True,
        'diagnostic_failures':DIAGNOSTIC_FAILURES}).encode())


def finish(receipts,lease):
    try:
        if OWNED_ROOT:
            try:private_file(ROOT/'receipts.json',json.dumps(receipts,indent=2).encode())
            finally:cleanup()
    finally:os.close(lease)


def main():
    require(socket.gethostname()=='fashionfindrs-dev','VM_ONLY')
    addresses=json.loads(subprocess.check_output(['ip','-j','address'],timeout=10))
    require(any(a.get('local')=='192.168.1.130' for item in addresses for a in item.get('addr_info',[])),'TARGET_DENIED')
    lease=os.open('/var/lock/plane-rehearsal-runtime.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        os.close(lease);raise
    receipts=[]
    try:
        prepare()
        private_file(ROOT/'restore-integrity.json',json.dumps(baseline('before-migration')).encode())
        start_store();sdk('restore')
        app_cli(args=['migrate','--noinput'])
        seed=Path(__file__).with_name('seed_shared_fixture.py').read_text()
        private_file(ROOT/'fixture.json',app_cli(code=seed).stdout)
        baseline('seeded-before-backup',preserve_only=True)
        private_file(ROOT/'good-fixture.dump',pg('pg_dump','plane_fixture_m',('--format=custom','--no-owner','--no-acl')).stdout)
        start_api()
        run([sys.executable,str(Path(__file__).with_name('inspect_shared_runtime.py'))])
        identity={'target':'192.168.1.130','application_revision':REVISION,'backend_image':BACKEND,
            'postgres_image':PG,'redis_image':REDIS,'test_image':RUNNER,'internal_network':True,'published_ports':False,
            'code_sha256':{p:hashlib.sha256((SOURCE_TREE/p).read_bytes()).hexdigest() for p in
             ['tools/plane_restore.py']+['docs/verification/HLB-434/native/'+n for n in
              ['shared_fixture_rehearsal.py','seed_shared_fixture.py','test_shared_fixture_m.py','inspect_shared_runtime.py','shared_fixture_m.json','shared_asset_sdk.py','asset_fixture.py','test_asset_store.py']]}}
        private_file(ROOT/'runtime-identity.json',json.dumps(identity,indent=2).encode())
        receipts.append(test_phase('pass-known-state'))
        sdk('corrupt')
        receipts.append(test_phase('failure-corrupt-associated-asset',fault=True))
        sdk('restore-fixture')
        remove_container(NS+'-api')
        pg('pg_restore','plane_fixture_m',('--clean','--if-exists','--no-owner','--no-acl','--exit-on-error'),(ROOT/'good-fixture.dump').read_bytes())
        expected=ROOT/'readbacks/seeded-before-backup.jsonl'
        baseline('restored-from-saved-dump',preserve_only=True)
        roundtrip=run([sys.executable,str(SOURCE_TREE/'tools/plane_restore.py'),'compare-database',
            '--expected',str(expected),'--actual',str(ROOT/'readbacks/restored-from-saved-dump.jsonl'),
            '--expected-sha256',hashlib.sha256(expected.read_bytes()).hexdigest()])
        private_file(ROOT/'roundtrip-integrity.json',roundtrip.stdout)
        start_api()
        receipts.append(test_phase('restore-and-repeat'))
        private_file(ROOT/'preservation.json',json.dumps(baseline('after-recovery',preserve_only=True)).encode())
    finally:finish(receipts,lease)
    print(json.dumps({'result':'PASS','phases':receipts,'full_restore_or_release_admitted':False}))


if __name__=='__main__':main()
