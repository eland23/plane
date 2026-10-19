#!/usr/bin/env python3
"""Read back actual isolation/image state while the database rehearsal is alive."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

if not __debug__:raise RuntimeError('OPTIMIZED_EXECUTION_DENIED')
NS='plane-rehearsal-m-434-20261019'
OWNER='HLB-434-shared-m-20261019'
ROOT=Path('/var/lib/plane-release')/OWNER
IMAGES={'minio':'sha256:30cfd6ed962109b44a4bf2122e0b64c172feaf5453f9eb30888eda03585ee50f','db':'sha256:468d34fefd6338031787c7b8e94078975b3aaf4d66c7ead25c39cd3ba46a15c6',
        'redis':'sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2',
        'api':'sha256:1c54c4fbe69d3a38740e1d05a6c0d31387050c351f0848e62c33c0a71a7c5a84'}


def require(ok,code):
    if not ok:raise RuntimeError(code)


def main():
    require(socket.gethostname()=='fashionfindrs-dev','VM_ONLY')
    addresses=json.loads(subprocess.check_output(['ip','-j','address'],timeout=10))
    require(any(a.get('local')=='192.168.1.130' for item in addresses for a in item.get('addr_info',[])),'TARGET_DENIED')
    require(ROOT.is_dir() and not ROOT.is_symlink() and (ROOT/'owner').read_text()==OWNER,'OWNER_REQUIRED')
    deadline=time.monotonic()+60
    while True:
        p=subprocess.run(['docker','container','inspect',NS+'-api'],capture_output=True,timeout=10)
        if p.returncode==0:break
        require(time.monotonic()<deadline,'API_NOT_AVAILABLE_FOR_READBACK');time.sleep(2)
    network=json.loads(subprocess.check_output(['docker','network','inspect',NS+'-net'],timeout=10))[0]
    require(network['Internal'] and network['Labels'].get('io.plane.rehearsal.owner')==OWNER,'NETWORK_ISOLATION_FAILED')
    rows={}
    for suffix,image in IMAGES.items():
        info=json.loads(subprocess.check_output(['docker','container','inspect',NS+'-'+suffix],timeout=10))[0]
        cfg=info['HostConfig']
        require(info['Image']==image and info['State']['Running'],'IMAGE_OR_RUNNING_STATE_MISMATCH')
        require(info['Config']['Labels'].get('io.plane.rehearsal.owner')==OWNER,'OWNER_MISMATCH')
        require(cfg['ReadonlyRootfs'] and not cfg.get('PortBindings') and set(info['NetworkSettings']['Networks'])=={NS+'-net'} and info['NetworkSettings']['Networks'][NS+'-net']['NetworkID']==network['Id'],'CONTAINER_ISOLATION_FAILED')
        rows[suffix]={'image':info['Image'],'running':True,'read_only_rootfs':True,'published_ports':False,
                      'memory_limit_bytes':cfg['Memory'],'network_id':info['NetworkSettings']['Networks'][NS+'-net']['NetworkID']}
    result={'target':'192.168.1.130','internal_network':True,'network_id':network['Id'],'containers':rows,
            'observer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'status':'PASS'}
    path=ROOT/'independent-runtime.json'
    with path.open('xb') as output:
        path.chmod(0o600);output.write(json.dumps(result,indent=2).encode())
    print(json.dumps({'status':'PASS','containers':len(rows),'internal_network':True,'published_ports':False}))


if __name__=='__main__':main()
