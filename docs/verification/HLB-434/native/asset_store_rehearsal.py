#!/usr/bin/env python3
"""Isolated signed S3 restore/corruption/recovery component on .130 only."""
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

OWNER='HLB-434-assets-20261018'
NS='plane-rehearsal-434-assets-20261018'
ROOT=Path('/var/lib/plane-release')/OWNER
SOURCE=Path('/var/lib/plane-release/HLB-434-20261018/source.assets.tar')
ARCHIVE_SHA='df778660d7564f29eded43f1db31cdbda686e4f5526ef6df7f0143635e14547f'
APP='sha256:1c54c4fbe69d3a38740e1d05a6c0d31387050c351f0848e62c33c0a71a7c5a84'
RUNNER='sha256:25c7d4cbb046e0929072c2197f074222e7fe9e5b1f09c75e2e3e8dc36635560f'
MINIO='sha256:30cfd6ed962109b44a4bf2122e0b64c172feaf5453f9eb30888eda03585ee50f'
NETWORK=NS+'-net'
NAMES=[NS+'-minio',NS+'-sdk',NS+'-tests']
SOURCE_TREE=Path(__file__).resolve().parents[4]
OWNED=False
DIAGNOSTIC_FAILURES=[]


def require(condition,code):
    if not condition:raise RuntimeError(code)


def inspect(kind,name):
    result=subprocess.run(['docker',kind,'inspect',name],capture_output=True,timeout=30)
    if result.returncode==0:
        rows=json.loads(result.stdout)
        require(isinstance(rows,list) and len(rows)==1 and isinstance(rows[0],dict)
                and isinstance(rows[0].get('Id'),str),'INSPECTION_FAILED')
        return rows[0]
    listing=subprocess.run(['docker',kind,'ls',*(['-a'] if kind=='container' else []),
        '--no-trunc','--format','{{json .}}'],capture_output=True,timeout=30)
    require(listing.returncode==0,'INSPECTION_FAILED')
    names=set()
    for line in listing.stdout.splitlines():
        row=json.loads(line)
        if kind=='image':
            require(all(isinstance(row.get(k),str) for k in ['ID','Repository','Tag']),'INSPECTION_FAILED')
            names.update([row['ID'],row['Repository']+':'+row['Tag']])
        else:
            key='Names' if kind=='container' else 'Name'
            require(isinstance(row.get(key),str),'INSPECTION_FAILED');names.add(row[key])
    require(name not in names,'INSPECTION_FAILED')
    return None


def private(path,data):
    with path.open('xb') as stream:
        path.chmod(0o600);stream.write(data)


def run(argv,timeout=120,accepted=(0,),log_required=True):
    process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL,start_new_session=True)
    try:stdout,stderr=process.communicate(timeout=timeout)
    finally:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait()
    try:private(ROOT/'logs'/(secrets.token_hex(8)+'.log'),stdout+stderr)
    except OSError:
        if log_required:raise
        DIAGNOSTIC_FAILURES.append('DIAGNOSTIC_WRITE_FAILED')
    require(process.returncode in accepted,'FIXTURE_COMMAND_FAILED')
    return subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)


def remove(name):
    info=inspect('container',name)
    if info:
        require(info['Config']['Labels'].get('io.plane.rehearsal.owner')==OWNER,'FOREIGN_CONTAINER_DENIED')
        run(['docker','rm','-f','-v',name],log_required=False)
        require(inspect('container',name) is None,'CLEANUP_FAILED')


def sdk(action,readback=None,accepted=(0,)):
    folder=readback or ROOT/'scratch'
    argv=['docker','run','--rm','--name',NS+'-sdk','--hostname',NS+'-sdk',
        '--label','io.plane.rehearsal.owner='+OWNER,'--network',NETWORK,'--memory','256m',
        '--memory-swap','256m','--cpus','1','--pids-limit','64','--cap-drop','ALL',
        '--security-opt','no-new-privileges','--read-only','--tmpfs','/tmp:rw,nosuid,noexec,size=32m',
        '-e','PYTHONDONTWRITEBYTECODE=1','-v',str(SOURCE_TREE)+':/workspace:ro',
        '-v',str(SOURCE)+':/original/source.assets.tar:ro',
        '-v',str(ROOT/'connection.json')+':/private/connection.json:ro',
        '-v',str(folder)+':/readback','--entrypoint','python',APP,
        '/workspace/docs/verification/HLB-434/native/asset_store_sdk.py',action,
        '--connection','/private/connection.json','--archive','/original/source.assets.tar',
        '--expected-sha256',ARCHIVE_SHA]
    return run(argv,accepted=accepted)


def target_guard():
    require(socket.gethostname()=='fashionfindrs-dev','VM_ONLY')
    addresses=json.loads(subprocess.check_output(['ip','-j','address'],timeout=10))
    require(any(a.get('local')=='192.168.1.130' for item in addresses for a in item.get('addr_info',[])),'TARGET_DENIED')


def preflight():
    global OWNED
    target_guard()
    require(not ROOT.exists() and ROOT.resolve()==ROOT,'OUTPUT_EXISTS_OR_SYMLINK')
    require(all(inspect('container',name) is None for name in NAMES),'EXISTING_CONTAINER_DENIED')
    require(inspect('network',NETWORK) is None,'EXISTING_NETWORK_DENIED')
    for image in [APP,RUNNER,MINIO]:require(inspect('image',image) is not None,'PINNED_IMAGE_REQUIRED')
    require(inspect('image',APP)['Config']['Labels']['org.opencontainers.image.revision']==
            'e5c7acf098a890436ab6300f0bc8491c7dd22725','APPLICATION_REVISION_MISMATCH')
    require(SOURCE.is_file() and not SOURCE.is_symlink() and SOURCE.stat().st_mode&0o777==0o600,'PRIVATE_ARCHIVE_REQUIRED')
    sys.path.insert(0,str(SOURCE_TREE/'tools'))
    from plane_restore import verified_assets
    with verified_assets(SOURCE,ARCHIVE_SHA) as (_,manifest):
        count=len(manifest['objects']);size=sum(row['size'] for row in manifest['objects'])
        require(size<=16*1024**2,'COMPONENT_ASSET_CAPACITY')
    memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    require(int(memory['MemAvailable'].split()[0])>=768*1024,'COMPONENT_MEMORY_RESERVATION')
    require(shutil.disk_usage('/var/lib/docker').free>=512*1024**2,'COMPONENT_DISK_RESERVATION')
    ROOT.mkdir(mode=0o700);private(ROOT/'owner',OWNER.encode());OWNED=True
    for name in ['logs','evidence','readbacks','scratch']:(ROOT/name).mkdir(mode=0o700)
    private(ROOT/'source-integrity.json',json.dumps({'objects':count,'bytes':size,'archive_sha256':ARCHIVE_SHA}).encode())
    user='plane'+secrets.token_hex(8);password=secrets.token_urlsafe(32)
    private(ROOT/'minio.env',f'MINIO_ROOT_USER={user}\nMINIO_ROOT_PASSWORD={password}\nMINIO_BROWSER=off\nHOME=/tmp\n'.encode())
    private(ROOT/'connection.json',json.dumps({'endpoint':'http://'+NS+'-minio:9000',
        'bucket':'plane-rehearsal-hlb434-assets-20261018','access_key':user,'secret_key':password}).encode())
    version=run(['docker','run','--rm','--name',NS+'-tests','--label','io.plane.rehearsal.owner='+OWNER,
        '--network','none','--memory','128m','--memory-swap','128m','--pids-limit','64',
        '--read-only','--tmpfs','/tmp:rw,nosuid,noexec,size=16m',RUNNER,'python','-m','pytest','--version'])
    require(version.stdout.strip()==b'pytest 9.0.3','TEST_RUNNER_REQUIRED')
    run(['docker','network','create','--internal','--label','io.plane.rehearsal.owner='+OWNER,NETWORK])
    run(['docker','run','-d','--name',NS+'-minio','--label','io.plane.rehearsal.owner='+OWNER,
        '--network',NETWORK,'--memory','256m','--memory-swap','256m','--cpus','1','--pids-limit','128',
        '--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
        '--tmpfs','/tmp:rw,nosuid,noexec,size=32m','--tmpfs','/data:rw,nosuid,noexec,size=1g,uid=1000,gid=1000,mode=0700',
        '--env-file',str(ROOT/'minio.env'),'--entrypoint','minio',MINIO,
        'server','--address',':9000','--quiet','/data'])
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        result=sdk('ready',accepted=(0,1))
        if result.returncode==0:
            store=inspect('container',NS+'-minio');network=inspect('network',NETWORK)
            require(store['Image']==MINIO and network['Internal'] and
                    not store['HostConfig'].get('PortBindings') and store['HostConfig']['ReadonlyRootfs'],
                    'ISOLATION_IDENTITY_MISMATCH')
            files=['tools/plane_restore.py']+['docs/verification/HLB-434/native/'+name for name in
                   ['asset_store_rehearsal.py','asset_store_sdk.py','test_asset_store.py','asset_fixture.py']]
            identity={'target':'192.168.1.130','owner':OWNER,'object_store_image':store['Image'],
                'sdk_image':APP,'test_image':RUNNER,'internal_network':True,'published_ports':False,
                'read_only_rootfs':True,'store_memory_bytes':store['HostConfig']['Memory'],
                'sdk_runtime':json.loads(result.stdout),
                'code_sha256':{name:hashlib.sha256((SOURCE_TREE/name).read_bytes()).hexdigest() for name in files}}
            private(ROOT/'runtime-identity.json',json.dumps(identity,indent=2).encode())
            return
        remove(NS+'-sdk');time.sleep(2)
    raise RuntimeError('OBJECT_STORE_BOOTSTRAP_FAILED')


def phase(name,fault=False):
    folder=ROOT/'readbacks'/name;folder.mkdir(mode=0o700)
    sdk('snapshot',folder)
    argv=['docker','run','--rm','--name',NS+'-tests','--label','io.plane.rehearsal.owner='+OWNER,
        '--network','none','--memory','128m','--memory-swap','128m','--cpus','1','--pids-limit','64',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
        '--tmpfs','/tmp:rw,nosuid,noexec,size=16m','-e','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
        '-e','PYTHONDONTWRITEBYTECODE=1','-v',str(SOURCE_TREE)+':/workspace:ro',
        '-v',str(SOURCE)+':/original/source.assets.tar:ro','-v',str(folder)+':/readback:ro',
        '-v',str(ROOT/'evidence')+':/evidence',RUNNER,'python','-m','pytest',
        '/workspace/docs/verification/HLB-434/native/test_asset_store.py','-q','-o','addopts=',
        '-p','no:cacheprovider','--junitxml=/evidence/'+name+'.xml']
    result=run(argv,accepted=(1,) if fault else (0,))
    private(ROOT/'evidence'/(name+'.log'),result.stdout+result.stderr)
    suites=list(ET.parse(ROOT/'evidence'/(name+'.xml')).getroot().iter('testsuite'))
    counts={k:sum(int(s.get(k,'0')) for s in suites) for k in ['tests','failures','errors','skipped']}
    require(counts=={'tests':4,'failures':1 if fault else 0,'errors':0,'skipped':0},'WRONG_TEST_RESULT')
    if fault:require(b'Fixture asset bytes must match golden SHA-256' in result.stdout,'WRONG_FAULT_ASSERTION')
    return {'phase':name,'exit':result.returncode,'counts':counts,'intended_checksum_failure':fault}


def cleanup():
    require((ROOT/'owner').read_text()==OWNER,'FOREIGN_ROOT_DENIED')
    store=inspect('container',NS+'-minio')
    if store:
        require(store['Config']['Labels'].get('io.plane.rehearsal.owner')==OWNER,'FOREIGN_CONTAINER_DENIED')
        try:run(['docker','logs',NS+'-minio'],log_required=False)
        except (OSError,RuntimeError,subprocess.SubprocessError):
            DIAGNOSTIC_FAILURES.append('STORE_LOG_COLLECTION_FAILED')
    for name in reversed(NAMES):remove(name)
    network=inspect('network',NETWORK)
    if network:
        require(network['Labels'].get('io.plane.rehearsal.owner')==OWNER and not network['Containers'],'FOREIGN_NETWORK_DENIED')
        run(['docker','network','rm',NETWORK],log_required=False);require(inspect('network',NETWORK) is None,'CLEANUP_FAILED')
    if (ROOT/'readbacks').exists():shutil.rmtree(ROOT/'readbacks',ignore_errors=False)
    for name in ['connection.json','minio.env']:(ROOT/name).unlink(missing_ok=True)
    require(hashlib.sha256(SOURCE.read_bytes()).hexdigest()==ARCHIVE_SHA,'ORIGINAL_ARCHIVE_CHANGED')
    private(ROOT/'cleanup.json',json.dumps({'containers_remaining':0,'network_removed':True,
        'ephemeral_object_store_removed':True,'readbacks_and_credential_files_removed':True,
        'original_archive_preserved':True,'private_diagnostics_retained':not DIAGNOSTIC_FAILURES,
        'diagnostic_failures':DIAGNOSTIC_FAILURES}).encode())


def finish(receipts,lease):
    try:
        if OWNED:
            try:private(ROOT/'receipts.json',json.dumps(receipts,indent=2).encode())
            finally:cleanup()
    finally:os.close(lease)


def main():
    target_guard()
    lease=os.open('/var/lock/plane-rehearsal-runtime.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        os.close(lease);raise
    receipts=[]
    try:
        preflight();sdk('restore')
        receipts.append(phase('pass-known-state'))
        sdk('corrupt');receipts.append(phase('failure-corrupt-asset',True))
        # Restore only the deliberately changed run-owned fixture object.
        sdk('restore-fixture')
        receipts.append(phase('restore-and-repeat'))
    finally:finish(receipts,lease)
    print(json.dumps({'result':'PASS','phases':receipts,'full_restore_or_release_admitted':False}))


if __name__=='__main__':main()
