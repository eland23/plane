"""Literal fixture-M contracts against real authenticated APIs and asset bytes."""
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,Request,build_opener

import pytest
from asset_fixture import FIXTURES

G=json.loads(Path(__file__).with_name('shared_fixture_m.json').read_text())
NS='plane-rehearsal-m-434-20261019'
BASE='http://'+NS+'-api:8000'
W='/api/workspaces/'+G['workspace']['slug']+'/'
P=W+'projects/'+G['project']['id']+'/'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def request(path,role='owner'):
    headers={}
    if role:
        session=json.loads(Path('/private/fixture.json').read_text())
        headers['Cookie']=session['cookie_name']+'='+session['sessions'][role]
    try:response=build_opener(NoRedirect()).open(Request(BASE+path,headers=headers),timeout=30)
    except HTTPError as error:response=error
    with response:
        return response.status,dict(response.headers),response.read() if response.status in [200,302] else b''


def data(path,role='owner'):
    status,_,body=request(path,role)
    assert status==200,f'Fixture M API read must succeed; got {status}'
    return json.loads(body)


def rows(path):
    value=data(path)
    return value if isinstance(value,list) else value['results']


def test_anonymous_wiki_read_is_denied():assert request(W+'pages/',None)[0]==401

def test_viewer_can_read_public_wiki():assert request(W+'pages/'+G['wiki']['id']+'/','viewer')[0]==200

def test_outsider_cannot_read_fixture_wiki():assert request(W+'pages/'+G['wiki']['id']+'/','outsider')[0]==403

def test_fixture_member_cannot_read_other_workspace():assert request('/api/workspaces/'+G['other_workspace']['slug']+'/pages/')[0]==403


@pytest.mark.parametrize('expected',G['issues'],ids=lambda row:'FAS-'+str(row['sequence']))
def test_six_issue_identities_states_parents_dates_and_modules_survive(expected):
    row=data(P+'issues/'+expected['id']+'/')
    assert {key:row[key] for key in ['id','name','sequence_id','state_id','parent_id','target_date','module_ids','cycle_id','sort_order']}=={
        'id':expected['id'],'name':expected['name'],'sequence_id':expected['sequence'],
        'state_id':G['states'][expected['state']]['id'],'parent_id':expected['parent'],
        'target_date':expected['target_date'],'module_ids':[G['modules'][expected['module']]] if expected['module'] else [],
        'cycle_id':G['cycle']['id'],'sort_order':expected['sort_order']},'Fixture M issue fields must match golden identities and graph'


@pytest.mark.parametrize('module,expected_sequences',[('Alpha',[2,5]),('Beta',[11,17,21])])
def test_modules_preserve_exact_membership(module,expected_sequences):
    actual=rows(P+'modules/'+G['modules'][module]+'/issues/')
    assert sorted(row['sequence_id'] for row in actual)==expected_sequences


def test_cycle_spans_dst_and_preserves_state_counts():
    row=data(P+'cycles/'+G['cycle']['id']+'/')
    assert row['start_date']==G['cycle']['start'] and row['end_date']==G['cycle']['end']
    assert (row['total_issues'],row['completed_issues'],row['unstarted_issues'],row['cancelled_issues'])==(6,2,2,2)


def test_cycle_membership_preserves_all_six_and_numeric_order():
    actual=rows(P+'cycles/'+G['cycle']['id']+'/cycle-issues/?order_by=sequence_id')
    assert [row['sequence_id'] for row in actual]==[2,5,11,17,21,30]


@pytest.mark.parametrize('index,key,target',[(2,'blocked_by',0),(3,'relates_to',1),(5,'duplicate',0)])
def test_blocking_related_and_duplicate_edges_survive(index,key,target):
    value=data(P+'issues/'+G['issues'][index]['id']+'/issue-relation/')
    assert [row['id'] for row in value[key]]==[G['issues'][target]['id']]


def test_thread_retains_inactive_author_and_parent():
    actual={row['id']:row for row in rows(P+'issues/'+G['issues'][2]['id']+'/comments/')}
    for expected in G['comments']:
        row=actual[expected['id']]
        assert (row['comment_html'],row['parent'],row['actor'])==(expected['html'],expected['parent'],expected['actor'])


def test_wiki_content_and_inline_asset_reference_survive():
    row=data(W+'pages/'+G['wiki']['id']+'/')
    path='/api/assets/v2/workspaces/'+G['workspace']['slug']+'/projects/'+G['project']['id']+'/'+G['assets']['inline']+'/'
    assert row['description_html']==G['wiki']['html']+'<img src="'+path+'">'


def test_document_is_discovered_from_issue_link_and_retains_association():
    links=rows(P+'issues/'+G['issues'][2]['id']+'/issue-links/')
    assert len(links)==1 and links[0]['id']==G['document']['link_id']
    location=urlsplit(links[0]['url'])
    assert location.hostname=='fixture-m.invalid'
    row=data(location.path+'?track_visit=false')
    assert (row['id'],row['description_html'],row['issue_ids'])==(G['document']['id'],G['document']['html'],[G['issues'][2]['id']])
    assert G['document']['id'] not in [p['id'] for p in rows(W+'pages/')]


@pytest.mark.parametrize('name,index',[('inline',0),('binary',1)])
def test_associated_assets_download_through_authenticated_api_and_match_golden_bytes(name,index):
    if name=='inline':path='/api/assets/v2/workspaces/'+G['workspace']['slug']+'/projects/'+G['project']['id']+'/'+G['assets'][name]+'/'
    else:path='/api/assets/v2/workspaces/'+G['workspace']['slug']+'/projects/'+G['project']['id']+'/issues/'+G['issues'][2]['id']+'/attachments/'+G['assets'][name]+'/'
    status,headers,_=request(path)
    assert status==302,'Authenticated fixture asset must produce a signed redirect'
    signed=headers['Location'];target=urlsplit(signed)
    assert not target.username and not target.password and not target.fragment
    assert target.scheme=='http' and target.hostname==NS+'-minio' and target.port==9000 and target.path=='/plane-rehearsal-hlb434-m-20261019/'+FIXTURES[index]['key']
    # No session cookie is forwarded to the storage host.
    with build_opener(NoRedirect()).open(signed,timeout=30) as response:
        body=response.read(1024*1024)
        assert response.headers['Content-Type']==FIXTURES[index]['headers']['ContentType']
    assert hashlib.sha256(body).hexdigest()==FIXTURES[index]['sha256'],'Associated fixture asset bytes must match golden SHA-256'


def test_anonymous_attachment_download_is_denied():
    path='/api/assets/v2/workspaces/'+G['workspace']['slug']+'/projects/'+G['project']['id']+'/issues/'+G['issues'][2]['id']+'/attachments/'+G['assets']['binary']+'/'
    assert request(path,None)[0]==401


def test_second_member_can_read_module_collection():
    assert request(P+'modules/','member')[0]==200
