"""Public asset export/transport contracts with literal synthetic bytes and URLs."""
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from linear_export import SourceError
from test_linear_coverage import snapshot, IDS
from test_linear_associations import GraphSource, TEAM, ORG

IMAGE='https://uploads.linear.app/fixture/image.png?signature=private-signature'
FILE='https://uploads.linear.app/fixture/file.bin'
PR='https://github.com/example/project/pull/42'
PAYLOAD=b'fashionfindr\x00asset\n'
SHA='f26551ed9e18adabe11e642f9200dd7d6b96dffdfb52433844ca2b7a8c2bdccd'

@pytest.fixture
def assets():
    spec=importlib.util.spec_from_file_location('linear_assets',Path(__file__).resolve().parents[1]/'linear_assets.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class Response(io.BytesIO):
    status=200
    def __init__(self,url,data=PAYLOAD,length=None):
        super().__init__(data);self.url=url;self.headers={'Content-Length':str(len(data) if length is None else length)}
    def geturl(self):return self.url
    def read1(self,size):return self.read(size)

class Opener:
    def __init__(self,data=PAYLOAD,length=None):self.calls=[];self.data=data;self.length=length
    def open(self,request,timeout):
        self.calls.append(request)
        return Response(request.full_url,self.data,self.length)

class Metadata(GraphSource):
    def __init__(self,mode=None):super().__init__();self.mode=mode
    def __call__(self,q,v):
        if 'AssetAttachments' not in q:return super().__call__(q,v)
        self.calls.append((q,v))
        nodes=[]
        if v['id']==IDS[0]:
            nodes=[{'id':'90000000-0000-0000-0000-000000000001','url':FILE,'title':'Fixture file','metadata':{},'issue':{'id':IDS[0],'team':{'id':TEAM}}}]
        if self.mode=='foreign' and nodes:nodes[0]['issue']['team']['id']=ORG
        return {'data':{'issue':{'id':v['id'],'team':{'id':TEAM},'attachments':{'nodes':nodes,'pageInfo':{'hasNextPage':False,'endCursor':None}}}}}

def fixture(tmp_path):return snapshot(tmp_path/'source',extra_fields={'description':'![image]('+IMAGE+') [PR]('+PR+')'})


def test_asset_bytes_hash_durable_reference_and_pr_link_are_preserved(assets,tmp_path):
    inputs=fixture(tmp_path);source=Metadata();opener=Opener()
    result=assets.export_assets(source,assets.AssetHTTP('private-token',opener=opener),*inputs,tmp_path/'assets')
    assert result['status']=='COMPLETE_FOR_DISCOVERED_ASSETS'
    assert len(result['assets'])==2
    assert all(r['sha256']==SHA and r['size']==19 for r in result['assets'])
    assert len(list((tmp_path/'assets').glob('sha256-*')))==1
    assert (tmp_path/'assets'/('sha256-'+SHA)).read_bytes()==PAYLOAD
    assert any(r['url']==PR and r['disposition']=='reference_link' for r in result['references'])
    assert all(r.full_url in [IMAGE,FILE] for r in opener.calls)
    assert all(r.get_header('Authorization')=='private-token' for r in opener.calls)
    assert all('private-token' not in p.read_text(errors='ignore') for p in (tmp_path/'assets').glob('*.json'))
    assert (tmp_path/'assets').stat().st_mode&0o777==0o700
    assert all(p.stat().st_mode&0o077==0 for p in (tmp_path/'assets').iterdir())
    assert all('mutation' not in q.lower() for q,v in source.calls)


def test_completed_asset_resume_verifies_bytes_without_redownload(assets,tmp_path):
    inputs=fixture(tmp_path);output=tmp_path/'assets';opener=Opener()
    first=assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=opener),*inputs,output)
    checkpoint=(output/'manifest.json').read_bytes()
    source=Metadata();again=Opener()
    second=assets.export_assets(source,assets.AssetHTTP('secret',opener=again),*inputs,output,resume=True)
    assert len(source.calls)==1 and not again.calls
    assert (output/'manifest.json').read_bytes()==checkpoint
    assert first['assets']==second['assets']
    assert second['status']=='COMPLETE_FOR_DISCOVERED_ASSETS'


@pytest.mark.parametrize('url',['http://uploads.linear.app/x','https://uploads.linear.app.evil.test/x',
 'https://uploads.linear.app@127.0.0.1/x','https://127.0.0.1/x','https://[::1]/x',
 'https://uploads.linear.app:444/x','https://uploads.linear.app/x#secret','https://uploads.linear.app/x\nHeader: injected'])
def test_disallowed_url_never_receives_credentials(assets,url):
    opener=Opener()
    with pytest.raises(SourceError,match='ASSET_URL_DENIED'):
        assets.AssetHTTP('secret',opener=opener).open(url)
    assert opener.calls==[]


def test_oversize_stream_cleanup_then_resume_with_correct_limits(assets,tmp_path):
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    with pytest.raises(SourceError,match='ASSET_TOO_LARGE'):
        assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output,max_asset_bytes=8)
    failed=json.loads((output/'manifest.json').read_text())
    assert failed['status']=='FAILED' and not list(output.glob('.part-*'))
    result=assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True)
    assert result['status']=='COMPLETE_FOR_DISCOVERED_ASSETS'
    assert all(r['sha256']==SHA for r in result['assets'])


def test_corrupt_committed_blob_rejected_without_mutating_checkpoint(assets,tmp_path):
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output)
    saved=(output/'manifest.json').read_bytes();blob=output/('sha256-'+SHA);blob.write_bytes(b'corrupted')
    with pytest.raises(SourceError,match='ASSET_CHECKSUM_MISMATCH'):
        assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True)
    assert (output/'manifest.json').read_bytes()==saved
    blob.write_bytes(PAYLOAD)
    assert assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True)['status']=='COMPLETE_FOR_DISCOVERED_ASSETS'


def test_truncated_stream_never_commits_blob(assets,tmp_path):
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    with pytest.raises(SourceError,match='ASSET_LENGTH_MISMATCH'):
        assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener(length=100)),*inputs,output)
    assert not list(output.glob('sha256-*')) and not list(output.glob('.part-*'))


def test_foreign_attachment_is_denied_before_private_page_commit(assets,tmp_path):
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    with pytest.raises(SourceError,match='ASSET_SCOPE'):
        assets.export_assets(Metadata('foreign'),assets.AssetHTTP('secret',opener=Opener()),*inputs,output)
    assert not list(output.glob('page-*.json'))


def test_external_image_is_explicitly_blocked_without_fetch(assets,tmp_path):
    inputs=snapshot(tmp_path/'source',extra_fields={'description':'![image](https://evil.test/image.png)'})
    result=assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,tmp_path/'assets')
    assert result['status']=='COMPLETE_WITH_BLOCKED_ASSETS'
    assert any(r['code']=='ASSET_URL_DENIED' and r['status']=='BLOCKED' for r in result['assets'])


def test_cancel_removes_partial_stream_and_resume_keeps_metadata(assets,tmp_path):
    class CancelResponse(Response):
        def read1(self,size):raise KeyboardInterrupt()
    class CancelOpener(Opener):
        def open(self,request,timeout):return CancelResponse(request.full_url)
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    with pytest.raises(SourceError,match='INTERRUPTED'):
        assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=CancelOpener()),*inputs,output)
    assert not list(output.glob('.part-*'))
    assert json.loads((output/'manifest.json').read_text())['status']=='FAILED'
    source=Metadata()
    result=assets.export_assets(source,assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True)
    assert len(source.calls)==1 and result['status']=='COMPLETE_FOR_DISCOVERED_ASSETS'


def test_redirect_is_denied_without_forwarding_authorization(assets):
    from urllib.error import HTTPError
    class Redirect(Opener):
        def open(self,request,timeout):
            self.calls.append(request)
            raise HTTPError(request.full_url,302,'private body',{'Location':'http://127.0.0.1/private'},io.BytesIO(b'private body'))
    opener=Redirect()
    with pytest.raises(SourceError,match='ASSET_HTTP_302'):
        assets.AssetHTTP('secret',opener=opener).open(IMAGE)
    assert len(opener.calls)==1 and opener.calls[0].full_url==IMAGE


def test_attachment_pagination_retains_second_page_and_denies_cursor_loop(assets,tmp_path):
    class Pages(Metadata):
        def __call__(self,q,v):
            result=super().__call__(q,v)
            if 'AssetAttachments' in q and v['id']==IDS[0]:
                connection=result['data']['issue']['attachments']
                if v['after'] is None:
                    connection['pageInfo']={'hasNextPage':True,'endCursor':'next-page'}
                else:
                    connection['nodes'][0]['id']='90000000-0000-0000-0000-000000000002'
                    connection['nodes'][0]['url']=PR
            return result
    inputs=fixture(tmp_path);source=Pages()
    result=assets.export_assets(source,assets.AssetHTTP('secret',opener=Opener()),*inputs,tmp_path/'assets')
    assert len(result['pages'])==7
    assert sum('AssetAttachments' in q and v['after']=='next-page' for q,v in source.calls)==1
    assert any(r['owner']==['attachment','90000000-0000-0000-0000-000000000002','url'] for r in result['references'])
    class Loop(Pages):
        def __call__(self,q,v):
            result=super().__call__(q,v)
            if 'AssetAttachments' in q and v['after']=='next-page':
                result['data']['issue']['attachments']['pageInfo']={'hasNextPage':True,'endCursor':'next-page'}
            return result
    with pytest.raises(SourceError,match='ASSET_CURSOR_LOOP'):
        assets.export_assets(Loop(),assets.AssetHTTP('secret',opener=Opener()),*inputs,tmp_path/'loop')
    assert len(list((tmp_path/'loop').glob('page-*.json')))==1


def test_rich_image_field_and_html_image_cannot_silently_become_reference_links(assets,tmp_path):
    inputs=snapshot(tmp_path/'source',extra_fields={'description':'<img src="https://evil.test/html.png">',
                                                  'bodyData':{'attrs':{'src':'https://evil.test/rich.png'}}})
    opener=Opener()
    result=assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=opener),*inputs,tmp_path/'assets')
    assert {r['url'] for r in result['assets'] if r['status']=='BLOCKED'}=={'https://evil.test/html.png','https://evil.test/rich.png'}
    assert all(r.full_url==FILE for r in opener.calls)


def test_rejected_resume_plan_preserves_original_checkpoint(assets,tmp_path):
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output)
    path=output/'manifest.json';data=json.loads(path.read_text());data['assets'][0]['url']='https://uploads.linear.app/tampered'
    path.write_text(json.dumps(data));saved=path.read_bytes()
    with pytest.raises(SourceError,match='ASSET_MANIFEST_SHAPE'):
        assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True)
    assert path.read_bytes()==saved


@pytest.mark.parametrize('content',[{'description':'<img src="//evil.test/a.png">'},
 {'description':'![x](file:///tmp/a.png)'},{'bodyData':{'attrs':{'src':'ftp://evil.test/a.png'}}}])
def test_non_http_image_references_remain_explicitly_blocked(assets,tmp_path,content):
    inputs=snapshot(tmp_path/'source',extra_fields=content);opener=Opener()
    result=assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=opener),*inputs,tmp_path/'assets')
    assert result['status']=='COMPLETE_WITH_BLOCKED_ASSETS'
    assert any(e['status']=='BLOCKED' for e in result['assets'])
    assert all(r.full_url==FILE for r in opener.calls)


@pytest.mark.parametrize('change',['duplicate_key','owner','budget'])
def test_rejected_resume_structure_and_budget_leave_checkpoint_unchanged(assets,tmp_path,change):
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output)
    path=output/'manifest.json';data=json.loads(path.read_text());kwargs={}
    if change=='duplicate_key':data['assets'].append(data['assets'][0])
    elif change=='owner':data['assets'][0]['owners']=[['issue',IDS[1],'description']]
    else:kwargs['max_total_bytes']=sum((output/p['file']).stat().st_size for p in data['pages'])+sum(e['size'] for e in data['assets'])-1
    path.write_text(json.dumps(data));saved=path.read_bytes()
    with pytest.raises(SourceError):
        assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True,**kwargs)
    assert path.read_bytes()==saved


@pytest.mark.parametrize('mode',['auth','limit'])
def test_metadata_failure_preserves_checkpoint_and_corrected_resume(assets,tmp_path,mode):
    class Denied(Metadata):
        def __call__(self,q,v):
            if 'AssetAttachments' in q and v['id']==IDS[1]:return {'errors':[{'message':'private-provider-error'}]}
            return super().__call__(q,v)
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    source=Denied() if mode=='auth' else Metadata()
    with pytest.raises(SourceError):
        assets.export_assets(source,assets.AssetHTTP('secret',opener=Opener()),*inputs,output,max_pages=1 if mode=='limit' else 100)
    data=json.loads((output/'manifest.json').read_text())
    assert len(data['pages'])==1 and data['status']=='FAILED'
    assert 'private-provider-error' not in (output/'manifest.json').read_text()
    source=Metadata()
    result=assets.export_assets(source,assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True)
    assert result['status']=='COMPLETE_FOR_DISCOVERED_ASSETS'
    assert not any('AssetAttachments' in q and v['id']==IDS[0] for q,v in source.calls)


def test_lock_and_no_overwrite_preserve_existing_source_and_assets(assets,tmp_path):
    import fcntl
    inputs=fixture(tmp_path);output=tmp_path/'assets'
    originals={p:p.read_bytes() for d in inputs for p in d.iterdir() if p.is_file()}
    assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output)
    saved=(output/'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output)
    with (output/'.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(SourceError,match='EXPORT_LOCKED'):
            assets.export_assets(Metadata(),assets.AssetHTTP('secret',opener=Opener()),*inputs,output,resume=True)
    assert (output/'manifest.json').read_bytes()==saved
    assert all(p.read_bytes()==raw for p,raw in originals.items())


@pytest.mark.parametrize('url',['https://github.com/example/project/actions/runs/42',
 'https://app.notion.com/page', 'http://192.168.1.130:3100/preview'])
def test_external_attachment_resources_remain_links_without_fetch(assets,tmp_path,url):
    class External(Metadata):
        def __call__(self,q,v):
            result=super().__call__(q,v)
            if 'AssetAttachments' in q:
                for node in result['data']['issue']['attachments']['nodes']:node['url']=url
            return result
    inputs=fixture(tmp_path);opener=Opener()
    result=assets.export_assets(External(),assets.AssetHTTP('secret',opener=opener),*inputs,tmp_path/'assets')
    assert result['status']=='COMPLETE_FOR_DISCOVERED_ASSETS'
    assert len(result['assets'])==1
    assert any(r['url']==url and r['owner'][0]=='attachment' for r in result['references'])
    assert all(r.full_url==IMAGE for r in opener.calls)
