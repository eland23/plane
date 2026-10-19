"""Public readonly restore-integrity command contracts; synthetic inputs only."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

TOOL = Path(__file__).resolve().parents[1] / 'plane_restore.py'
KEY_DIGEST = '3547531dbd8928b5554af2f790e6e6587a5977485ddfffd37c226fab57ec1c29'
CONTENT_DIGEST = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
MEMBER = 'objects/' + KEY_DIGEST + '.bin'


def archive_fixture(tmp_path, *, content=b'abc', objects=None, extra=None, overrides=None, include_object=True, manifest_body=None):
    path = tmp_path/'backup.tar'
    row = {'archive_path':MEMBER,'key':'private/key.bin','size':3,'sha256':CONTENT_DIGEST,
           'etag':'opaque-etag','last_modified':'2026-10-18T12:00:00+00:00',
           'headers':{'ContentType':'application/octet-stream','Metadata':{'private':'private-value'}}}
    row.update(overrides or {})
    manifest = {'bucket':'private-bucket','objects':[row] if objects is None else objects}
    with tarfile.open(path,'w') as stream:
        entries=[('manifest.json',json.dumps(manifest).encode() if manifest_body is None else manifest_body)]
        if include_object:entries.append((MEMBER,content))
        for name,body in [*entries,*(extra or [])]:
            member=name if isinstance(name,tarfile.TarInfo) else tarfile.TarInfo(name)
            member.size=len(body) if member.isfile() else 0
            stream.addfile(member,io.BytesIO(body) if member.isfile() else None)
    return path,hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args):
    result=subprocess.run([sys.executable,str(TOOL),*map(str,args)],capture_output=True,text=True,timeout=10)
    parsed=json.loads(result.stdout)
    assert 'private/key.bin' not in result.stdout and 'private-value' not in result.stdout
    assert not result.stderr
    return result.returncode,parsed


def test_valid_archive_audit_reports_only_integrity_metadata(tmp_path):
    path,digest=archive_fixture(tmp_path)
    code,result=command('audit-assets','--archive',path,'--expected-sha256',digest)
    assert code==0
    assert result=={'status':'PASS','objects':1,'bytes':3,'archive_sha256':digest}


def test_downloaded_asset_matches_original_then_rejects_changed_bytes_and_recovers(tmp_path):
    path,digest=archive_fixture(tmp_path)
    readback=tmp_path/'readback.bin'
    arguments=['compare-asset','--archive',path,'--expected-sha256',digest,
               '--key-sha256',KEY_DIGEST,'--readback',readback]
    readback.write_bytes(b'abc')
    code,result=command(*arguments)
    assert code==0
    assert result=={'status':'PASS','key_sha256':KEY_DIGEST,'sha256':CONTENT_DIGEST,'bytes':3}
    readback.write_bytes(b'xyz')
    assert command(*arguments)==(1,{'status':'FAIL','error':'ASSET_HASH_MISMATCH'})
    readback.write_bytes(b'abc')
    assert command(*arguments)==(0,result)


@pytest.mark.parametrize('options,error',[
    ({'content':b'xyz'},'ASSET_HASH_MISMATCH'),
    ({'include_object':False},'ASSET_OBJECT_MISSING'),
    ({'extra':[(MEMBER,b'abc')]},'ARCHIVE_MEMBER_DUPLICATE'),
    ({'extra':[('../escape',b'abc')]},'ARCHIVE_MEMBER_UNEXPECTED'),
    ({'overrides':{'archive_path':'../escape'}},'ASSET_ARCHIVE_PATH_INVALID'),
    ({'overrides':{'sha256':'g'*64}},'ASSET_DIGEST_INVALID'),
    ({'overrides':{'size':True}},'ASSET_SIZE_INVALID'),
    ({'overrides':{'size':512*1024**2+1}},'ASSET_SIZE_INVALID'),
    ({'overrides':{'size':4}},'ASSET_SIZE_MISMATCH'),
    ({'overrides':{'headers':{'Metadata':{'unsafe':'header\nvalue'}}}},'ASSET_METADATA_INVALID'),
    ({'manifest_body':b'{"bucket":"a","bucket":"b","objects":[]}'},'MANIFEST_INVALID'),
])
def test_malformed_or_corrupt_archive_fails_without_extracting_or_exposing_values(tmp_path,options,error):
    path,digest=archive_fixture(tmp_path,**options)
    assert command('audit-assets','--archive',path,'--expected-sha256',digest)==(1,{'status':'FAIL','error':error})
    assert not (tmp_path.parent/'escape').exists()


def test_archive_symlink_member_is_never_followed(tmp_path):
    link=tarfile.TarInfo('host-file');link.type=tarfile.SYMTYPE;link.linkname='/etc/passwd'
    path,digest=archive_fixture(tmp_path,extra=[(link,b'')])
    assert command('audit-assets','--archive',path,'--expected-sha256',digest)==(1,{'status':'FAIL','error':'ARCHIVE_MEMBER_INVALID'})


def test_original_archive_digest_is_required_before_manifest_is_trusted(tmp_path):
    path,_=archive_fixture(tmp_path)
    assert command('audit-assets','--archive',path,'--expected-sha256','0'*64)==(1,{'status':'FAIL','error':'ARCHIVE_HASH_MISMATCH'})


def test_empty_bucket_is_valid_without_extra_members(tmp_path):
    path,digest=archive_fixture(tmp_path,objects=[],include_object=False)
    code,result=command('audit-assets','--archive',path,'--expected-sha256',digest)
    assert code==0 and result['objects']==0 and result['bytes']==0


def test_nonregular_archive_is_rejected_without_blocking(tmp_path):
    import os
    path=tmp_path/'fifo';os.mkfifo(path)
    assert command('audit-assets','--archive',path,'--expected-sha256','0'*64)==(1,{'status':'FAIL','error':'REGULAR_INPUT_REQUIRED'})


def test_archive_input_symlink_is_rejected(tmp_path):
    path,digest=archive_fixture(tmp_path)
    link=tmp_path/'alias.tar';link.symlink_to(path)
    assert command('audit-assets','--archive',link,'--expected-sha256',digest)==(1,{'status':'FAIL','error':'INPUT_UNAVAILABLE_OR_INVALID'})


def test_oversize_sparse_input_is_rejected_before_reading(tmp_path):
    path=tmp_path/'huge.tar'
    with path.open('wb') as stream:stream.truncate(2*1024**3+1)
    assert command('audit-assets','--archive',path,'--expected-sha256','0'*64)==(1,{'status':'FAIL','error':'INPUT_TOO_LARGE'})


def snapshot_file(path, tables):
    path.write_text(''.join(json.dumps({'table':table,'rows':rows})+'\n' for table,rows in tables.items()))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_database_compare_checks_exact_values_then_allows_only_explicit_additions(tmp_path):
    expected=tmp_path/'expected.jsonl';actual=tmp_path/'actual.jsonl'
    source={'issues':[{'id':'fixture-1','name':'Original issue','nullable':None,'body':{'items':['first','second']}}],
            'pages':[]}
    digest=snapshot_file(expected,source);snapshot_file(actual,source)
    arguments=['compare-database','--expected',expected,'--actual',actual,'--expected-sha256',digest]
    code,result=command(*arguments)
    assert code==0
    assert result=={'status':'PASS','tables':2,'original_rows':1,'mode':'exact','original_values_preserved':True}
    upgraded={'issues':[dict(source['issues'][0],new_field=None),{'id':'fixture-2','name':'New issue','nullable':None,'body':None,'new_field':None}],
              'pages':[],'new_table':[{'id':'new-schema-row'}]}
    snapshot_file(actual,upgraded)
    assert command(*arguments)==(1,{'status':'FAIL','error':'SNAPSHOT_TABLE_SET_MISMATCH'})
    assert command(*arguments,'--allow-additions')==(0,dict(result,mode='preserve'))


@pytest.mark.parametrize('actual,error',[
    ({},'ORIGINAL_TABLE_LOST'),
    ({'issues':[]},'ORIGINAL_ROW_CHANGED'),
    ({'issues':[{'id':'fixture-1','name':'Changed','nullable':None,'body':{'items':['first','second']}}]},'ORIGINAL_ROW_CHANGED'),
    ({'issues':[{'id':'fixture-1','name':'Original issue','nullable':None,'body':{'items':['second','first']}}]},'ORIGINAL_ROW_CHANGED'),
    ({'issues':[{'id':'fixture-1','name':'Original issue','body':{'items':['first','second']}}]},'ORIGINAL_COLUMNS_LOST'),
])
def test_preservation_rejects_lost_tables_columns_records_or_nested_values(tmp_path,actual,error):
    expected=tmp_path/'expected.jsonl';readback=tmp_path/'actual.jsonl'
    digest=snapshot_file(expected,{'issues':[{'id':'fixture-1','name':'Original issue','nullable':None,
        'body':{'items':['first','second']}}]})
    snapshot_file(readback,actual)
    assert command('compare-database','--expected',expected,'--actual',readback,'--expected-sha256',digest,
                   '--allow-additions')==(1,{'status':'FAIL','error':error})


def test_preservation_retains_duplicate_row_multiplicity(tmp_path):
    expected=tmp_path/'expected.jsonl';actual=tmp_path/'actual.jsonl'
    digest=snapshot_file(expected,{'rows':[{'value':'same'},{'value':'same'}]})
    snapshot_file(actual,{'rows':[{'value':'same'}]})
    assert command('compare-database','--expected',expected,'--actual',actual,'--expected-sha256',digest,
                   '--allow-additions')==(1,{'status':'FAIL','error':'ORIGINAL_ROW_CHANGED'})


def test_exact_snapshot_ignores_database_row_order_but_preserves_json_types(tmp_path):
    expected=tmp_path/'expected.jsonl';actual=tmp_path/'actual.jsonl'
    rows=[{'id':1,'value':True},{'id':2,'value':False}]
    digest=snapshot_file(expected,{'rows':rows});snapshot_file(actual,{'rows':list(reversed(rows))})
    args=['compare-database','--expected',expected,'--actual',actual,'--expected-sha256',digest]
    assert command(*args)[0]==0
    snapshot_file(actual,{'rows':[{'id':1,'value':1},{'id':2,'value':False}]})
    assert command(*args)==(1,{'status':'FAIL','error':'SNAPSHOT_ROW_MISMATCH'})


@pytest.mark.parametrize('readback,error',[
    ('{"table":"rows","rows":[]}\n{"table":"rows","rows":[]}\n','SNAPSHOT_TABLE_DUPLICATE'),
    ('{"table":"rows","rows":[{"id":1},{"other":2}]}\n','SNAPSHOT_SCHEMA_INVALID'),
    ('{"table":"rows","rows":[{"secret":"private-user-token-keep-out","value":NaN}]}\n','SNAPSHOT_INVALID'),
    ('{"table":"rows","rows":{},"unexpected":true}\n','SNAPSHOT_INVALID'),
])
def test_invalid_readback_reports_fixed_code_without_private_values(tmp_path,readback,error):
    expected=tmp_path/'expected.jsonl';actual=tmp_path/'actual.jsonl'
    digest=snapshot_file(expected,{'rows':[]});actual.write_text(readback)
    code,result=command('compare-database','--expected',expected,'--actual',actual,'--expected-sha256',digest)
    assert code==1 and result=={'status':'FAIL','error':error}
    assert 'private-user-token-keep-out' not in json.dumps(result)
