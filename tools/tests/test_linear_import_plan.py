"""Public read-only dry-run contracts; all source identifiers are synthetic."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from linear_export import SourceError

@pytest.fixture
def planner():
    spec=importlib.util.spec_from_file_location('linear_import_plan',Path(__file__).resolve().parents[1]/'linear_import_plan.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_snapshot_transport_is_fixed_authenticated_and_rejects_non_readonly_response(planner):
    calls=[]
    class Result:
        returncode=0
        stdout=json.dumps({'schema_version':1,'read_only':True,'tables':{},'rows':{}})
        stderr=''
    def run(command,**kwargs):calls.append((command,kwargs));return Result()
    snapshot=planner.PlaneSnapshotSSH(run=run).capture()
    assert snapshot['read_only'] is True
    assert calls[0][0][-2:]==['root@192.168.1.129','docker exec -i plane-app-api-1 python -']
    assert 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY' in calls[0][1]['input']
    Result.stdout=json.dumps({'schema_version':1,'read_only':False,'tables':{},'rows':{}})
    with pytest.raises(SourceError,match='DESTINATION_NOT_READ_ONLY'):
        planner.PlaneSnapshotSSH(run=run).capture()

from test_linear_coverage import snapshot, inventory, IDS
from test_linear_assets import Metadata, Opener
import linear_coverage
import linear_assets

WS='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
PROJECT='8bdb658d-abeb-5f8c-9cc4-2a8da509c980'


def inputs(root, **kwargs):
    issues,associations=snapshot(root/'source',**kwargs)
    schema=inventory(root/'schema')
    coverage=root/'coverage'
    linear_coverage.compare_exports(issues,associations,issues,associations,schema,coverage)
    assets=root/'assets'
    linear_assets.export_assets(Metadata(),linear_assets.AssetHTTP('synthetic-token',opener=Opener()),issues,associations,assets)
    return issues,associations,assets,coverage


def destination():
    columns={'id':'uuid','workspace_id':'uuid','project_id':'uuid','external_source':'text','external_id':'text','sequence_id':'integer','sequence':'integer','issue_id':'uuid','identifier':'text'}
    tables={name:{'columns':dict(columns),'count':0,'sha256':'0'*64} for name in ['workspaces','projects','issues','issue_sequences','modules','cycles','labels','states','pages','initiatives','module_milestones','issue_links','issue_attachments']}
    return {'schema_version':1,'read_only':True,'tables':tables,
            'rows':{'workspaces':[{'id':WS,'slug':'synthetic'}],'projects':[],'issues':[],'issue_sequences':[]}}


class Destination:
    def __init__(self,value=None,after=None):
        self.value=copy.deepcopy(value or destination());self.after=copy.deepcopy(after);self.calls=0
        for snapshot in [self.value,self.after]:
            if snapshot is not None:
                for table,rows in snapshot['rows'].items():
                    if table in snapshot['tables']:snapshot['tables'][table]['count']=len(rows)
    def capture(self):
        self.calls+=1
        return copy.deepcopy(self.after if self.calls>1 and self.after is not None else self.value)


def test_dry_run_keeps_source_uuid_display_number_and_destination_uuid_separate(planner,tmp_path):
    source=inputs(tmp_path);reader=Destination()
    report=planner.plan_import(*source,reader,WS,tmp_path/'plan')
    issues=[r for r in report['mapping'] if r['source_kind']=='issue']
    assert [r['source_identifier'] for r in issues]==['FAS-2','FAS-5','FAS-11','FAS-17','FAS-21','FAS-30']
    assert [r['sequence_id'] for r in issues]==[2,5,11,17,21,30]
    first=issues[0]
    assert first['source_uuid']==IDS[0] and first['destination_uuid']=='cddf4a22-061d-51e6-b918-6bd701187e5d'
    assert report['target']['project_uuid']==PROJECT and report['target']['action']=='create'
    assert report['counts']['issue']==6 and report['next_sequence_id']==31
    assert report['destination_unchanged'] is True and reader.calls==2
    assert report['can_import'] is False


def test_reserved_number_collision_blocks_and_correction_restores_identical_plan(planner,tmp_path):
    source=inputs(tmp_path);dest=destination()
    dest['rows']['projects']=[{'id':PROJECT,'workspace_id':WS,'identifier':'FAS'}]
    dest['rows']['issue_sequences']=[{'id':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','project_id':PROJECT,'issue_id':None,'sequence':11,'deleted':True}]
    blocked=planner.plan_import(*source,Destination(dest),WS,tmp_path/'blocked',target_project=PROJECT)
    assert {'code':'NUMBER_COLLISION','source_uuid':IDS[2],'sequence_id':11} in blocked['blockers']
    assert blocked['plan_valid'] is False
    dest['rows']['issue_sequences']=[]
    corrected=planner.plan_import(*source,Destination(dest),WS,tmp_path/'corrected',target_project=PROJECT)
    repeated=planner.plan_import(*source,Destination(dest),WS,tmp_path/'repeated',target_project=PROJECT)
    assert corrected==repeated and corrected['plan_valid'] is True
    assert corrected['next_sequence_id']==31


def test_missing_schema_and_parent_reference_are_named_not_silently_dropped(planner,tmp_path):
    missing='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'
    source=inputs(tmp_path,extra_fields={'parent':{'id':missing,'identifier':'FAS-99','team':{'id':'00000000-0000-0000-0000-000000000001'}}})
    dest=destination();del dest['tables']['pages']
    report=planner.plan_import(*source,Destination(dest),WS,tmp_path/'plan')
    assert {'code':'MISSING_SCHEMA_TABLE','kind':'document','table':'pages'} in report['blockers']
    assert {'code':'UNRESOLVED_REFERENCE','kind':'issue','source_uuid':IDS[0],'field':'parent','target_kind':'issue','target_uuid':missing} in report['blockers']
    assert report['plan_valid'] is False and len(report['unresolved_references'])==6


def test_destination_drift_is_named_and_prevents_a_stable_plan(planner,tmp_path):
    source=inputs(tmp_path);before=destination();after=copy.deepcopy(before)
    after['tables']['issues']['sha256']='f'*64
    report=planner.plan_import(*source,Destination(before,after),WS,tmp_path/'plan')
    assert report['destination_unchanged'] is False and report['plan_valid'] is False
    assert report['destination_changes'][0]['table']=='issues'


def test_attachment_identity_and_source_bytes_are_included_in_proposed_counts(planner,tmp_path):
    source=inputs(tmp_path);report=planner.plan_import(*source,Destination(),WS,tmp_path/'plan')
    assert report['counts']['attachment']==1
    row=next(r for r in report['mapping'] if r['source_kind']=='attachment')
    assert row['source_uuid']=='90000000-0000-0000-0000-000000000001'
    assert row['destination_kind']=='issue_attachment'
    assert report['proposed_counts']['issue_attachment']==1


@pytest.mark.parametrize('table,field', [('issues','project_id'),('issues','sequence_id'),('issue_sequences','sequence'),('issue_sequences',None)])
def test_numbering_infrastructure_is_required_even_for_empty_destination(planner,tmp_path,table,field):
    source=inputs(tmp_path);dest=destination()
    if field:del dest['tables'][table]['columns'][field]
    else:del dest['tables'][table];del dest['rows'][table]
    report=planner.plan_import(*source,Destination(dest),WS,tmp_path/'plan')
    assert report['plan_valid'] is False
    assert any(b['table']==table and (not field or b.get('field')==field) for b in report['blockers'])


@pytest.mark.parametrize('binding', [dict(external_source='linear:other',external_id='other'),dict(external_source='linear:00000000-0000-0000-0000-000000000002',external_id=None)])
def test_explicit_project_rejects_foreign_or_partial_source_binding(planner,tmp_path,binding):
    source=inputs(tmp_path);dest=destination()
    dest['rows']['projects']=[dict(id=PROJECT,workspace_id=WS,identifier='FAS',**binding)]
    report=planner.plan_import(*source,Destination(dest),WS,tmp_path/'plan',target_project=PROJECT)
    assert {'code':'PROJECT_SOURCE_ID_COLLISION'} in report['blockers']
    assert report['plan_valid'] is False


@pytest.mark.parametrize('table', ['issue_attachments','issue_links'])
def test_identity_inventory_cannot_be_omitted_when_records_exist(planner,table):
    dest=Destination().capture();dest['tables'][table]['count']=1
    with pytest.raises(SourceError,match='DESTINATION_INVENTORY_MISSING'):
        planner.validated_snapshot(dest)


def test_attachment_source_identity_reuses_exact_record_and_rejects_occupied_uuid(planner,tmp_path):
    source=inputs(tmp_path);clean=planner.plan_import(*source,Destination(),WS,tmp_path/'clean')
    attachment=next(r for r in clean['mapping'] if r['source_kind']=='attachment')
    dest=destination()
    dest['rows']['issue_attachments']=[dict(id=attachment['destination_uuid'],workspace_id=WS,project_id=PROJECT,
        external_source='linear:00000000-0000-0000-0000-000000000002',external_id=attachment['source_uuid'])]
    reused=planner.plan_import(*source,Destination(dest),WS,tmp_path/'reused')
    assert reused['reused_identity_counts']['issue_attachment']==1
    dest['rows']['issue_attachments'][0]['external_id']='90000000-0000-0000-0000-000000000099'
    blocked=planner.plan_import(*source,Destination(dest),WS,tmp_path/'blocked')
    assert {'code':'DESTINATION_UUID_COLLISION','kind':'attachment','source_uuid':attachment['source_uuid']} in blocked['blockers']


def test_private_assets_are_verified_before_destination_access_and_outputs_never_overwrite(planner,tmp_path):
    source=inputs(tmp_path);reader=Destination()
    planner.plan_import(*source,reader,WS,tmp_path/'plan')
    first=(tmp_path/'plan/manifest.json').read_bytes()
    assert (tmp_path/'plan').stat().st_mode & 0o777==0o700
    for name in ['manifest.json','destination-before.json','destination-after.json']:
        assert (tmp_path/'plan'/name).stat().st_mode & 0o777==0o600
    with pytest.raises(SourceError,match='PLAN_INPUT_OR_IO'):
        planner.plan_import(*source,reader,WS,tmp_path/'plan')
    assert (tmp_path/'plan/manifest.json').read_bytes()==first
    manifest=json.loads((source[2]/'manifest.json').read_text())
    blob=source[2]/next(a['file'] for a in manifest['assets'] if a['status']=='ARCHIVED')
    blob.write_bytes(b'changed');reader=Destination()
    with pytest.raises(SourceError,match='ASSET_CHECKSUM_MISMATCH'):
        planner.plan_import(*source,reader,WS,tmp_path/'bad')
    assert reader.calls==0 and not (tmp_path/'bad').exists()


def test_one_fas_project_two_modules_cross_module_parent_and_unassigned_issue(planner,tmp_path):
    from test_linear_associations import GraphSource, response, TEAM, ORG, CYCLE
    import linear_export, linear_associations
    modules=['20000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000002']
    nodes=[]
    for index,(key,number) in enumerate(zip(IDS,[2,5,11,17,21,30])):
        node=dict(id=key,identifier='FAS-'+str(number),team={'id':TEAM},title='Fixture')
        if index<5:node['project']={'id':modules[index%2]}
        if index==1:node['parent']={'id':IDS[0],'identifier':'FAS-2','team':{'id':TEAM}}
        node['cycle']={'id':CYCLE};nodes.append(node)
    source=GraphSource({
        'ExportIssues':{'data':{'issues':{'nodes':nodes,'pageInfo':{'hasNextPage':False,'endCursor':None}}}},
        'Association_team_projects':response(TEAM,[{'id':m,'name':'Module '+str(i)} for i,m in enumerate(modules)]),
        'Association_project_detail':lambda v:{'data':{'entity':{'id':v['id'],'name':'Module '+str(modules.index(v['id']))}}},
        'Association_team_cycles':response(TEAM,[{'id':CYCLE,'team':{'id':TEAM}}]),
        'Association_cycle_detail':{'data':{'entity':{'id':CYCLE,'name':'Shared cycle','team':{'id':TEAM}}}},
        'Association_issue_documents':lambda v:response(v['id'],[]),
    })
    issues=tmp_path/'issues';associations=tmp_path/'associations'
    linear_export.export_issues(source,TEAM,issues);linear_associations.export_associations(source,issues,associations)
    schema=inventory(tmp_path/'schema');coverage=tmp_path/'coverage';assets=tmp_path/'assets'
    linear_coverage.compare_exports(issues,associations,issues,associations,schema,coverage)
    linear_assets.export_assets(Metadata(),linear_assets.AssetHTTP('synthetic-token',opener=Opener()),issues,associations,assets)
    report=planner.plan_import(issues,associations,assets,coverage,Destination(),WS,tmp_path/'plan')
    assert report['plan_valid'] is True
    assert report['proposed_counts']['project']==1 and report['proposed_counts']['module']==2
    assert report['issue_placement']=={'module_assigned':5,'module_free':1}
    assert len({r['project_uuid'] for r in report['mapping'] if r['source_kind']=='issue'})==1
    parent=next(r for r in report['links'] if r['field']=='parent')
    assert parent['source_uuid']==IDS[1] and parent['target_uuid']==IDS[0] and parent['disposition']=='native_proposal'
    assert report['proposed_counts']['cycle']==1


def test_existing_name_collision_is_not_merged_by_name(planner,tmp_path):
    source=inputs(tmp_path);dest=destination()
    dest['rows']['projects']=[{'id':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','workspace_id':WS,'identifier':'OTHER','name':'Fixture team'}]
    report=planner.plan_import(*source,Destination(dest),WS,tmp_path/'plan')
    assert {'code':'DESTINATION_NAME_COLLISION','kind':'team','source_uuid':'00000000-0000-0000-0000-000000000001','table':'projects'} in report['blockers']
    assert report['target']['action']=='create'


def test_independent_receipt_checker_detects_number_loss(planner,tmp_path):
    from verify_linear_import_plan import verify
    source=inputs(tmp_path);planner.plan_import(*source,Destination(),WS,tmp_path/'plan')
    assert verify(source[0],tmp_path/'plan')['verified_issue_count']==6
    path=tmp_path/'plan/manifest.json';report=json.loads(path.read_text())
    next(r for r in report['mapping'] if r['source_kind']=='issue')['sequence_id']=1
    path.write_text(json.dumps(report))
    with pytest.raises(AssertionError,match='number changed'):verify(source[0],tmp_path/'plan')
    import subprocess
    result=subprocess.run([sys.executable,'-O',str(Path(planner.__file__).with_name('verify_linear_import_plan.py')),'--issues',str(source[0]),'--output',str(tmp_path/'plan')],capture_output=True,text=True)
    assert result.returncode==1 and 'RECEIPT_VERIFICATION_FAILED' in result.stdout


def test_cli_exit_and_sanitized_transport_failure(planner,tmp_path,monkeypatch,capsys):
    source=inputs(tmp_path)
    args=[]
    for name,path in zip(['issues','associations','assets','coverage'],source):args+=['--'+name,str(path)]
    args+=['--workspace',WS,'--output',str(tmp_path/'plan')]
    monkeypatch.setattr(planner,'PlaneSnapshotSSH',Destination)
    assert planner.main(args)==3
    assert 'Synthetic original' not in capsys.readouterr().out
    def fail(*args,**kwargs):raise planner.subprocess.TimeoutExpired('private details',90)
    # Exercise the fixed transport independently: subprocess diagnostics never escape.
    spec=importlib.util.spec_from_file_location('transport',Path(planner.__file__))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with pytest.raises(SourceError,match='^DESTINATION_SNAPSHOT_FAILED$'):module.PlaneSnapshotSSH(run=fail).capture()


def test_identifier_reservation_inventory_accepts_plane_integer_primary_key(planner):
    dest=destination()
    dest['tables']['project_identifiers']={'columns':{'id':'bigint','workspace_id':'uuid','project_id':'uuid','name':'text'},'count':1,'sha256':'0'*64}
    dest['rows']['project_identifiers']=[dict(id=1,workspace_id=WS,project_id=PROJECT,name='FAS')]
    assert planner.validated_snapshot(Destination(dest).capture())['rows']['project_identifiers'][0]['id']==1
    dest['rows']['project_identifiers'][0]['id']='invalid'
    with pytest.raises(SourceError):planner.validated_snapshot(Destination(dest).capture())


def test_cancelled_snapshot_and_unknown_workspace_preserve_input_without_output(planner,tmp_path):
    source=inputs(tmp_path);before=(source[0]/'manifest.json').read_bytes()
    class Cancelled(Destination):
        def capture(self):
            if self.calls:raise KeyboardInterrupt()
            return super().capture()
    with pytest.raises(KeyboardInterrupt):planner.plan_import(*source,Cancelled(),WS,tmp_path/'cancelled')
    with pytest.raises(SourceError,match='DESTINATION_WORKSPACE'):
        planner.plan_import(*source,Destination(),'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',tmp_path/'unknown')
    assert not (tmp_path/'cancelled').exists() and not (tmp_path/'unknown').exists()
    assert (source[0]/'manifest.json').read_bytes()==before
