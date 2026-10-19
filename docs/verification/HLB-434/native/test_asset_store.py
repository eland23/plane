"""Unchanged assertions against private authenticated S3 readback snapshots."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from asset_fixture import FIXTURES

if not __debug__:
    raise RuntimeError('OPTIMIZED_EXECUTION_DENIED')

ARCHIVE=Path('/original/source.assets.tar')
READBACK=Path('/readback')
EXPECTED_ARCHIVE='df778660d7564f29eded43f1db31cdbda686e4f5526ef6df7f0143635e14547f'
TOOL=Path('/workspace/tools/plane_restore.py')


def original_rows():
    with tarfile.open(ARCHIVE) as stream:
        return json.load(stream.extractfile('manifest.json'))['objects']


def snapshot():
    return json.loads((READBACK/'objects.json').read_text())


def test_object_store_requires_authenticated_requests():
    assert snapshot()['anonymous_status']==403,'Anonymous fixture download must be denied'


def test_all_original_and_fixture_object_keys_are_present_exactly():
    expected=[hashlib.sha256(row['key'].encode()).hexdigest() for row in original_rows()]
    expected.extend(row['key_sha256'] for row in FIXTURES)
    actual=[row['key_sha256'] for row in snapshot()['objects']]
    assert sorted(actual)==sorted(expected),'Original and fixture key identities must match exactly'


def test_original_and_fixture_object_metadata_is_preserved():
    expected={hashlib.sha256(row['key'].encode()).hexdigest():row['headers'] for row in original_rows()}
    expected.update({row['key_sha256']:row['headers'] for row in FIXTURES})
    actual={row['key_sha256']:row['headers'] for row in snapshot()['objects']}
    matches=all(actual.get(key)==headers for key,headers in expected.items())
    assert matches,'Content headers and metadata must match the captured source'


def test_restored_asset_bytes_match_original_and_golden_hashes():
    for row in original_rows():
        key_digest=hashlib.sha256(row['key'].encode()).hexdigest()
        command=[sys.executable,str(TOOL),'compare-asset','--archive',str(ARCHIVE),
                 '--expected-sha256',EXPECTED_ARCHIVE,'--key-sha256',key_digest,
                 '--readback',str(READBACK/(key_digest+'.bin'))]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,'Original asset checksum gate must pass: '+result.stdout
    for row in FIXTURES:
        actual=hashlib.sha256((READBACK/(row['key_sha256']+'.bin')).read_bytes()).hexdigest()
        assert actual==row['sha256'],'Fixture asset bytes must match golden SHA-256'
