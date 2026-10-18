"""Snapshot/delta/coverage contracts use synthetic saved exports, never live issue IDs."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linear_export as issue_export
import linear_associations as association_export
from test_linear_associations import GraphSource, TEAM, ORG, DOC

IDS = ['10000000-0000-0000-0000-%012d' % n for n in [2, 5, 11, 17, 21, 30]]


@pytest.fixture
def coverage():
    spec = importlib.util.spec_from_file_location('linear_coverage', Path(__file__).resolve().parents[1] / 'linear_coverage.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(root, title='Synthetic original', missing=False, archive=False, document=True, schema_fields=None, project_change=False, extra_fields=None):
    nodes = [{'id': key, 'identifier': 'FAS-%d' % n, 'title': title if n == 2 else 'Fixture %d' % n,
              'team': {'id': TEAM}, 'archivedAt': '2026-10-18T00:00:00Z' if n == 11 and archive else None,
              'createdAt': '2026-01-01T00:00:00Z', 'updatedAt': '2026-10-17T00:00:00Z'}
             for key, n in zip(IDS, [2, 5, 11, 17, 21, 30]) if not (missing and n == 5)]
    for node in nodes:
        node.update(extra_fields or {})
    overrides = {
        'ExportIssues': {'data': {'issues': {'nodes': nodes, 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}},
        'Association_team_detail': {'data': {'entity': {'id': TEAM, 'name': 'Fixture team'}}},
        'Association_issue_documents': lambda v: {'data': {'entity': {'id': v['id'], 'connection': {'nodes': [{'id': DOC, 'title': 'Fixture doc', 'content': 'Private fixture café', 'issue': {'id': IDS[0]}}] if document and v['id'] == IDS[0] else [], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}},
    }
    if schema_fields is not None:
        overrides['Association_schema'] = {'data': {'entity': {'name': 'Issue', 'fields': [{'name': f} for f in schema_fields]}}}
    if project_change:
        project = '20000000-0000-0000-0000-000000000001'
        overrides['Association_team_projects'] = {'data': {'entity': {'id': TEAM, 'connection': {'nodes': [{'id': project, 'lead': {'id': ORG}}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}}
        overrides['Association_project_detail'] = {'data': {'entity': {'id': project, 'lead': None}}}
    class FixtureSource(GraphSource):
        def __call__(self, query, variables):
            if schema_fields is not None and 'query Association_schema ' in query:
                self.calls.append((query, variables))
                return overrides['Association_schema']
            return super().__call__(query, variables)
    source = FixtureSource(overrides)
    root.mkdir()
    issues, associations = root / 'issues', root / 'associations'
    issue_export.export_issues(source, TEAM, issues)
    association_export.export_associations(source, issues, associations)
    return issues, associations


def inventory(root):
    root.mkdir(mode=0o700)
    data = {'schema_version': 1, 'status': 'COMPLETE', 'organization_id': ORG, 'team_id': TEAM,
            'types': {'issue': {'type': 'Issue', 'status': 'available', 'fields': ['id', 'identifier', 'title', 'team', 'archivedAt', 'createdAt', 'updatedAt', 'customProperties']},
                      'document': {'type': 'Document', 'status': 'available', 'fields': ['id', 'title', 'content', 'issue']}}}
    p = root / 'manifest.json';p.write_text(json.dumps(data));p.chmod(0o600)
    return root


def test_concurrent_edit_archive_and_missing_record_are_named_without_inventing_deletion(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after', title='Synthetic changed', missing=True, archive=True)
    schema = inventory(tmp_path / 'schema')
    result = coverage.compare_exports(*before, *after, schema, tmp_path / 'report')
    assert result['comparison']['equal'] is False
    assert {'kind': 'issue', 'id': IDS[0], 'field': 'title'} in [{k:r[k] for k in ['kind','id','field']} for r in result['delta']['modified_fields']]
    assert {'kind': 'issue', 'id': IDS[2], 'field': 'archivedAt'} in [{k:r[k] for k in ['kind','id','field']} for r in result['delta']['modified_fields']]
    assert result['delta']['tombstone_candidates'] == [{'kind': 'issue', 'id': IDS[1], 'reason': 'deleted_or_access_lost_or_scope_changed', 'confirmed_deleted': False}]
    assert result['readiness']['cutover_ready'] is False
    assert all('Synthetic changed' not in json.dumps(r) for r in result['delta']['modified_fields'])


def test_schema_inventory_keeps_permission_and_unavailable_outcomes_explicit(coverage, tmp_path):
    class SchemaSource:
        def __call__(self, query, variables):
            if 'ExportScope' in query:
                return {'data': {'organization': {'id': ORG}, 'team': {'id': TEAM}}}
            if variables['name'] == 'DocumentContentHistoryType':
                return {'data': {'entity': None}}
            if variables['name'] == 'Comment':
                return {'errors': [{'message': 'private provider error'}]}
            return {'data': {'entity': {'name': variables['name'], 'fields': [{'name': 'id'}, {'name': 'createdAt'}]}}}
    output = tmp_path / 'schema'
    result = coverage.capture_schema(SchemaSource(), TEAM, output)
    assert result['types']['issue']['fields'] == ['createdAt', 'id']
    assert result['types']['documentHistory']['status'] == 'unavailable'
    assert result['types']['comment']['status'] == 'blocked'
    assert result['status'] == 'COMPLETE_WITH_BLOCKED_TYPES'
    assert 'private provider error' not in (output / 'manifest.json').read_text()
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output / 'manifest.json').stat().st_mode & 0o777 == 0o600


def test_coverage_classifies_archived_unread_unavailable_and_unsupported_fields(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after')
    schema = inventory(tmp_path / 'schema')
    path = schema / 'manifest.json';value = json.loads(path.read_text())
    value['types']['comment'] = {'type': 'Comment', 'status': 'blocked', 'fields': []}
    value['types']['documentHistory'] = {'type': coverage.CATEGORIES['documentHistory'], 'status': 'unavailable', 'fields': []}
    value['types']['document']['fields'].remove('content')
    path.write_text(json.dumps(value))
    result = coverage.compare_exports(*before, *after, schema, tmp_path / 'out')
    rows = {(r['kind'],r['field']):r for r in result['coverage']}
    assert rows['issue','title']['disposition'] == 'archive'
    assert rows['issue','customProperties']['disposition'] == 'blocked'
    assert rows['issue','customProperties']['usage'] == 'unknown'
    assert rows['comment','*']['disposition'] == 'blocked'
    assert rows['documentHistory','*']['disposition'] == 'unavailable'
    assert rows['document','content']['disposition'] == 'unsupported'
    assert not any(r['native_verified'] for r in rows.values())
    assert result['readiness']['cutover_ready'] is False


def test_missing_document_edge_is_reported_with_exact_direction(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after', document=False)
    result = coverage.compare_exports(*before, *after, inventory(tmp_path / 'schema'), tmp_path / 'out')
    assert result['delta']['removed_edges'] == [['issue', IDS[0], 'documents', 'document', DOC]]
    assert result['comparison']['exit_code'] == 1
    assert result['delta']['tombstone_candidates'] == [{'kind':'document','id':DOC,'reason':'deleted_or_access_lost_or_scope_changed','confirmed_deleted':False}]


def test_archive_event_after_cutoff_is_an_explicit_exception(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after', archive=True)
    result = coverage.compare_exports(*before, *after, inventory(tmp_path / 'schema'), tmp_path / 'out', cutoff='2026-10-17T12:00:00Z')
    assert {'kind':'issue','id':IDS[2],'field':'archivedAt','reason':'observed_event_after_requested_cutoff'} in result['exceptions']
    assert result['cutoff']['verified'] is False
    assert 'cutoff_exceptions' in result['readiness']['blockers']


def test_corrupt_or_incomplete_input_never_creates_a_completeness_report(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after')
    schema = inventory(tmp_path / 'schema')
    (after[1] / 'manifest.json').write_text('[]')
    with pytest.raises(issue_export.SourceError):
        coverage.compare_exports(*before, *after, schema, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()
    (after[1] / 'manifest.json').write_text('{bad json')
    with pytest.raises(issue_export.SourceError, match='SNAPSHOT_SHAPE'):
        coverage.compare_exports(*before, *after, schema, tmp_path / 'out')


def test_identical_snapshots_do_not_establish_independent_stability(coverage, tmp_path):
    same = snapshot(tmp_path / 'snapshot')
    result = coverage.compare_exports(*same, *same, inventory(tmp_path / 'schema'), tmp_path / 'out')
    assert result['comparison']['equal'] is True
    assert result['comparison']['independent_observations'] is False
    assert 'independent_repeat_snapshot_required' in result['readiness']['blockers']


def test_cli_returns_nonzero_for_named_loss_without_printing_private_payloads(coverage, tmp_path):
    import subprocess
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after', title='private changed title', document=False)
    schema = inventory(tmp_path / 'schema')
    result = subprocess.run([sys.executable, coverage.__file__, 'compare', '--before-issues', str(before[0]),
                             '--before-associations', str(before[1]), '--after-issues', str(after[0]),
                             '--after-associations', str(after[1]), '--schema', str(schema), '--output', str(tmp_path / 'out')],
                            capture_output=True, text=True)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert summary['delta_counts']['removed_edges'] == 1
    assert summary['cutover_ready'] is False
    assert 'private changed title' not in result.stdout + result.stderr
    assert 'Private fixture café' not in result.stdout + result.stderr
    assert (tmp_path / 'out/manifest.json').stat().st_mode & 0o777 == 0o600


def test_report_is_private_inputs_unchanged_and_repeat_never_overwrites(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after')
    schema = inventory(tmp_path / 'schema')
    originals = {p: p.read_bytes() for root in [*before,*after,schema] for p in root.iterdir() if p.is_file()}
    output = tmp_path / 'out'
    result = coverage.compare_exports(*before, *after, schema, output)
    assert result['comparison']['equal'] is True
    assert result['comparison']['independent_observations'] is True
    assert result['cutoff']['verified'] is False
    saved = (output / 'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        coverage.compare_exports(*before, *after, schema, output)
    assert (output / 'manifest.json').read_bytes() == saved
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(p.read_bytes() == raw for p, raw in originals.items())


def test_nested_field_capture_and_credential_exclusion_are_distinct(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after')
    schema = inventory(tmp_path / 'schema')
    path = schema / 'manifest.json';data = json.loads(path.read_text())
    data['types']['integration'] = {'type':'Integration','status':'available','fields':['id','accessToken']}
    path.write_text(json.dumps(data))
    result = coverage.compare_exports(*before,*after,schema,tmp_path / 'out')
    rows = {(r['kind'],r['field']):r for r in result['coverage']}
    assert rows['issue','team']['capture_state'] == 'partial_object_or_relation'
    assert rows['integration','accessToken']['disposition'] == 'unsupported'
    assert rows['integration','accessToken']['reason'] == 'credentials_excluded_by_migration_scope'
    assert rows['integration','accessToken']['owner_disposition_required'] is False
    assert result['feature_gaps']['custom_properties']['usage'] == 'unknown'
    assert result['feature_gaps']['custom_properties']['cutover_disposition_required'] is True


def test_schema_drift_is_not_hidden_when_record_values_are_unchanged(coverage, tmp_path):
    before = snapshot(tmp_path / 'before', schema_fields=['id','projectMilestone'])
    after = snapshot(tmp_path / 'after', schema_fields=['id','newField'])
    result = coverage.compare_exports(*before,*after,inventory(tmp_path / 'schema'),tmp_path / 'out')
    assert result['comparison']['equal'] is False
    assert result['delta']['schema_fields_added'] == ['newField']
    assert result['delta']['schema_fields_removed'] == ['projectMilestone']


def test_intra_snapshot_object_to_null_edit_is_not_silently_merged(coverage, tmp_path):
    before = snapshot(tmp_path / 'before')
    after = snapshot(tmp_path / 'after', project_change=True)
    result = coverage.compare_exports(*before,*after,inventory(tmp_path / 'schema'),tmp_path / 'out')
    assert any(r['kind']=='project' and r['field']=='lead' for r in result['intra_snapshot_conflicts']['after'])
    assert 'intra_snapshot_changes' in result['readiness']['blockers']


def test_completed_resume_does_not_create_an_independent_capture(coverage, tmp_path):
    import shutil
    before = snapshot(tmp_path / 'before')
    shutil.copytree(tmp_path / 'before', tmp_path / 'after')
    after = (tmp_path / 'after/issues', tmp_path / 'after/associations')
    original = (before[1] / 'manifest.json').read_bytes()
    source = GraphSource()
    association_export.export_associations(source, *after, resume=True)
    assert (after[1] / 'manifest.json').read_bytes() != original
    assert len(source.calls) == 1  # scope read only, no graph observations
    result = coverage.compare_exports(*before,*after,inventory(tmp_path / 'schema'),tmp_path / 'out')
    assert result['comparison']['equal'] is True
    assert result['comparison']['independent_observations'] is False
    assert 'independent_repeat_snapshot_required' in result['readiness']['blockers']


def test_coverage_empty_values_preserve_false_and_zero_as_populated(coverage, tmp_path):
    fields = {'emptyText':'', 'emptyList':[], 'emptyObject':{}, 'nullValue':None,
              'falseValue':False, 'zeroValue':0, 'textValue':'present',
              'emptyRelation':{'nodes':[], 'pageInfo':{'hasNextPage':False,'endCursor':None}}}
    before = snapshot(tmp_path / 'before', extra_fields=fields)
    after = snapshot(tmp_path / 'after', extra_fields=fields)
    schema = inventory(tmp_path / 'schema')
    path = schema / 'manifest.json';data = json.loads(path.read_text())
    data['types']['issue']['fields'].extend(fields)
    path.write_text(json.dumps(data))
    result = coverage.compare_exports(*before,*after,schema,tmp_path / 'out')
    rows = {r['field']:r for r in result['coverage'] if r['kind']=='issue'}
    for field in ['emptyText','emptyList','emptyObject','nullValue','emptyRelation']:
        assert rows[field]['field_present'] == 6
        assert rows[field]['field_populated'] == 0
        assert rows[field]['usage'] == 'null_or_empty'
    for field in ['falseValue','zeroValue','textValue']:
        assert rows[field]['field_populated'] == 6
        assert rows[field]['usage'] == 'populated'


def test_schema_auth_loss_stops_requests_and_retry_uses_new_private_output(coverage, tmp_path):
    calls = []
    def denied(query, variables):
        calls.append(variables)
        if 'ExportScope' in query:
            return {'data':{'organization':{'id':ORG},'team':{'id':TEAM}}}
        raise issue_export.SourceError('SOURCE_HTTP_403')
    result = coverage.capture_schema(denied,TEAM,tmp_path / 'denied')
    assert len(calls) == 2
    assert all(e['status']=='blocked' for e in result['types'].values())
    def allowed(query, variables):
        if 'ExportScope' in query:
            return {'data':{'organization':{'id':ORG},'team':{'id':TEAM}}}
        return {'data':{'entity':{'name':variables['name'],'fields':[{'name':'id'}]}}}
    retry = coverage.capture_schema(allowed,TEAM,tmp_path / 'retry')
    assert retry['status'] == 'COMPLETE'
    assert result['status'] == 'COMPLETE_WITH_BLOCKED_TYPES'


def test_schema_cancel_keeps_failed_checkpoint_and_no_false_success(coverage, tmp_path):
    def source(query, variables):
        if 'ExportScope' in query:
            return {'data':{'organization':{'id':ORG},'team':{'id':TEAM}}}
        raise KeyboardInterrupt()
    with pytest.raises(issue_export.SourceError, match='INTERRUPTED'):
        coverage.capture_schema(source,TEAM,tmp_path / 'cancel')
    result = json.loads((tmp_path / 'cancel/manifest.json').read_text())
    assert result['status'] == 'FAILED'
    assert result['failure_code'] == 'INTERRUPTED'
    assert result['types'] == {}
