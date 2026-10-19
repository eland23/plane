#!/usr/bin/env python3
"""Run over trusted SSH stdin on .130. No database, ports or external network."""
import sys
if not __debug__:
    print("OPTIMIZED_EXECUTION_DENIED", file=sys.stderr)
    raise SystemExit(2)

import json
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import tempfile

# Builder's classic image config ID is 0488a84e...; .130's containerd store
# exposes the imported OCI manifest ID. Bind it to all source rootfs layers and
# meaningful runtime configuration, not just mutable labels or a tag.
IMAGE = 'sha256:1c54c4fbe69d3a38740e1d05a6c0d31387050c351f0848e62c33c0a71a7c5a84'
PAYLOAD_SHA256 = '8e7ddf80e918f7a1360a43aeb0cbc68902ef33878ce2215b7bd6135e61ba94cc'
REVISION = 'e5c7acf098a890436ab6300f0bc8491c7dd22725'
TREE = '0f1626a2415b52b29ec661cca2958bb97275a9bc'
assert socket.gethostname() == 'fashionfindrs-dev', 'Dedicated VM required'
addresses = json.loads(subprocess.check_output(['ip', '-j', 'address']))
assert any(a.get('local') == '192.168.1.130' for item in addresses for a in item.get('addr_info', []))
info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', IMAGE]))[0]
assert info['Id'] == IMAGE
keys = ('Env','Cmd','Entrypoint','WorkingDir','User','Labels','ExposedPorts','Volumes','Healthcheck','Shell','StopSignal')
payload = {'rootfs': info['RootFS'], 'config': {key: info['Config'].get(key) for key in keys}}
assert hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == PAYLOAD_SHA256
assert info['Config']['Labels']['org.opencontainers.image.revision'] == REVISION
assert info['Config']['Labels']['io.plane.source.tree'] == TREE
memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
assert int(memory['MemAvailable'].split()[0]) >= 768 * 1024, 'Bounded CLI check reservation unavailable'
# This reservation is only for one short-lived CLI process. It does not admit a
# full application deployment or establish application peak memory requirements.
probe = '''
if not __debug__:
    raise SystemExit('OPTIMIZED_EXECUTION_DENIED')
import django, json, os, subprocess
from pathlib import Path
django.setup()
from django.core.management import call_command, get_commands
from django.db.migrations.loader import MigrationLoader
from plane.app.services import milestones
assert {'wait_for_db','wait_for_migrations','register_instance','configure_instance','create_bucket'} <= set(get_commands())
leaves = MigrationLoader(None).graph.leaf_nodes('db')
assert ('db', '0124_module_milestones') in leaves, leaves
for suffix in ('api','worker','beat','migrator'):
    path = Path('/code/bin/docker-entrypoint-' + suffix + '.sh')
    assert path.is_file() and os.access(path, os.X_OK)
    subprocess.run(['sh','-n',str(path)], check=True, capture_output=True)
call_command('check', verbosity=0)
print(json.dumps({'management_check':'PASS','migration_leaf':'0124_module_milestones','entrypoint_syntax':4,'native_milestone_import':'PASS'}))
'''
with tempfile.TemporaryDirectory(prefix='plane-rehearsal-command-', dir='/var/tmp') as directory:
    os.chmod(directory, 0o700)
    cidfile = Path(directory) / 'cid'
    try:
        result = subprocess.run(['docker', 'run', '--cidfile', str(cidfile),
            '--network', 'none', '--memory', '512m', '--memory-swap', '512m',
            '--cpus', '1', '--pids-limit', '128', '--read-only',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m',
            '--tmpfs', '/code/plane/logs:rw,noexec,nosuid,size=16m',
            '-e', 'DJANGO_SETTINGS_MODULE=plane.settings.test',
            '-e', 'SECRET_KEY=isolated-synthetic-command-probe-only',
            '-e', 'DATABASE_URL=postgresql://fixture:fixture@127.0.0.1:5432/unavailable',
            '-e', 'DEBUG=0', '-e', 'SCOUT_MONITOR=false', IMAGE, 'python', '-c', probe],
            capture_output=True, text=True, timeout=180)
        if result.returncode:
            # This fixture carries no real records or credentials. Retain bounded
            # diagnostics for command failures; never pass a live environment.
            print(result.stdout[-12000:])
            print(result.stderr[-12000:])
            raise SystemExit(result.returncode)
        payload = json.loads(result.stdout.splitlines()[-1])
        state = json.loads(subprocess.check_output(['docker', 'inspect', cidfile.read_text().strip()]))[0]
        assert not state['State']['OOMKilled']
        print(json.dumps({'image': IMAGE, 'payload_sha256': PAYLOAD_SHA256, 'revision': REVISION, 'tree': TREE,
            'result': payload, 'network': 'none', 'memory_limit_mib': 512,
            'deployment_admitted': False, 'api_and_database_proven': False}))
    finally:
        if cidfile.exists():
            cid = cidfile.read_text().strip()
            subprocess.run(['docker', 'rm', '-f', cid], check=True, capture_output=True)
            remaining = subprocess.check_output(['docker', 'container', 'ls', '-aq', '--no-trunc']).decode().split()
            assert cid not in remaining, 'Owned CLI container cleanup failed'
