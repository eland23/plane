"""Observable read-only association export contracts with synthetic provider data."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linear_export as base

TEAM = '00000000-0000-0000-0000-000000000001'
ORG = '00000000-0000-0000-0000-000000000002'
ISSUE = '10000000-0000-0000-0000-000000000002'
PROJECT = '20000000-0000-0000-0000-000000000001'
DOC = '30000000-0000-0000-0000-000000000001'


class Source:
    def __init__(self):
        self.calls = []

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        if 'ExportScope' in query:
            return {'data': {'organization': {'id': ORG}, 'team': {'id': TEAM}}}
        if 'ExportIssues' in query:
            return {'data': {'issues': {'nodes': [{'id': ISSUE, 'identifier': 'FAS-2', 'team': {'id': TEAM}, 'project': {'id': PROJECT}}],
                                       'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}
        if 'Association_issue_documents' in query:
            nodes = [{'id': DOC, 'title': 'Issue-only document', 'content': 'Synthetic café', 'issue': {'id': ISSUE}}]
        elif 'Association_project_detail' in query:
            return {'data': {'entity': {'id': PROJECT, 'name': 'Alpha'}}}
        elif 'Association_catalog_' in query:
            return {'data': {'entity': {'nodes': [], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}
        elif 'Association_schema' in query:
            return {'data': {'entity': {'name': 'Issue', 'fields': [{'name': 'id'}, {'name': 'projectMilestone'}]}}}
        else:
            nodes = []
        return {'data': {'entity': {'id': variables['id'], 'connection': {'nodes': nodes, 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}}


@pytest.fixture
def associations():
    spec = importlib.util.spec_from_file_location('linear_associations', Path(__file__).resolve().parents[1] / 'linear_associations.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_issue_association_discovers_document_when_team_projects_are_empty(associations, tmp_path):
    source = Source()
    issues = tmp_path / 'issues'
    base.export_issues(source, TEAM, issues)
    output = tmp_path / 'associations'
    result = associations.export_associations(source, issues, output)
    assert result['status'] == 'COMPLETE_FOR_ASSOCIATIONS'
    assert result['counts'].get('document', 0) == 1
    assert result['counts']['project'] == 1
    payloads = [json.loads((output / p['file']).read_text()) for p in result['pages']]
    assert any('Synthetic café' in json.dumps(p, ensure_ascii=False) for p in payloads)
    assert ['issue', ISSUE, 'documents', 'document', DOC] in result['edges']
    assert result['atomic_snapshot'] is False
    assert result['full_migration_backup'] is False
    assert all('mutation' not in query.lower() for query, _ in source.calls)

INITIATIVE = '40000000-0000-0000-0000-000000000001'
FOREIGN_PROJECT = '20000000-0000-0000-0000-000000000009'
CYCLE = '50000000-0000-0000-0000-000000000001'
LABEL = '60000000-0000-0000-0000-000000000001'
GROUP = '60000000-0000-0000-0000-000000000002'
MILESTONE = '70000000-0000-0000-0000-000000000001'
UPDATE = '80000000-0000-0000-0000-000000000001'


def response(key, nodes, more=False, cursor=None):
    return {'data': {'entity': {'id': key, 'connection': {'nodes': nodes, 'pageInfo': {'hasNextPage': more, 'endCursor': cursor}}}}}


class GraphSource(Source):
    def __init__(self, overrides=None):
        super().__init__()
        self.overrides = overrides or {}

    def __call__(self, query, variables):
        for operation, handler in self.overrides.items():
            if 'query ' + operation + '(' in query:
                self.calls.append((query, variables))
                return handler(variables) if callable(handler) else handler
        return super().__call__(query, variables)


def setup_issues(source, root):
    issues = root / 'issues'
    base.export_issues(source, TEAM, issues)
    return issues


def test_paginated_portfolio_retains_shared_documents_edges_and_foreign_stubs(associations, tmp_path):
    other_doc = '30000000-0000-0000-0000-000000000002'
    def documents(v):
        if v['cursor'] is None:
            return response(v['id'], [{'id': DOC, 'title': 'Shared', 'content': 'One'}], True, 'next-doc')
        assert v['cursor'] == 'next-doc'
        return response(v['id'], [{'id': other_doc, 'title': 'Archived', 'archivedAt': '2026-01-01T00:00:00Z'}])
    source = GraphSource({
        'Association_team_projects': response(TEAM, [{'id': PROJECT, 'name': 'Alpha'}]),
        'Association_project_initiatives': response(PROJECT, [{'id': INITIATIVE, 'name': 'Portfolio'}]),
        'Association_initiative_detail': {'data': {'entity': {'id': INITIATIVE, 'name': 'Portfolio'}}},
        'Association_initiative_projects': response(INITIATIVE, [{'id': PROJECT}, {'id': FOREIGN_PROJECT}]),
        'Association_project_documents': documents,
        'Association_project_projectMilestones': response(PROJECT, [{'id': MILESTONE, 'name': 'Launch', 'targetDate': '2026-12-01', 'project': {'id': PROJECT}}]),
        'Association_project_projectUpdates': response(PROJECT, [{'id': UPDATE, 'body': 'Saved update', 'user': {'id': ORG, 'name': 'Inactive author'}, 'project': {'id': PROJECT}}]),
    })
    result = associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    assert result['counts']['project'] == 1
    assert result['counts']['project_reference'] == 2
    assert result['counts']['initiative'] == 1
    assert result['counts']['document'] == 2
    assert result['counts']['milestone'] == 1
    assert result['counts']['projectUpdate'] == 1
    assert ['issue', ISSUE, 'documents', 'document', DOC] in result['edges']
    assert ['project', PROJECT, 'documents', 'document', DOC] in result['edges']
    assert not any(v.get('id') == FOREIGN_PROJECT for _, v in source.calls)
    assert all('includeArchived: true' in q for q, _ in source.calls if 'connection:' in q)


def test_cycle_timezone_payload_and_exclusive_label_group_are_retained(associations, tmp_path):
    source = GraphSource({
        'Association_team_cycles': response(TEAM, [{'id': CYCLE, 'team': {'id': TEAM}, 'startsAt': '2026-10-25T01:00:00+02:00', 'endsAt': '2026-11-01T01:00:00+01:00'}]),
        'Association_cycle_detail': {'data': {'entity': {'id': CYCLE, 'team': {'id': TEAM}, 'startsAt': '2026-10-25T01:00:00+02:00', 'endsAt': '2026-11-01T01:00:00+01:00'}}},
        'Association_team_labels': response(TEAM, [{'id': LABEL, 'team': None, 'parent': {'id': GROUP}}]),
        'Association_label_detail': lambda v: {'data': {'entity': {'id': v['id'], 'team': None, 'isGroup': v['id'] == GROUP, 'groupType': 'singleSelect'}}},
        'Association_label_children': lambda v: response(v['id'], [{'id': LABEL, 'team': None, 'parent': {'id': GROUP}}] if v['id'] == GROUP else []),
    })
    output = tmp_path / 'out'
    result = associations.export_associations(source, setup_issues(source, tmp_path), output)
    assert result['counts']['cycle'] == 1 and result['counts']['label'] == 2
    raw = ''.join((output / r['file']).read_text() for r in result['pages'])
    assert '2026-10-25T01:00:00+02:00' in raw and '2026-11-01T01:00:00+01:00' in raw
    assert 'singleSelect' in raw
    assert ['label', GROUP, 'children', 'label', LABEL] in result['edges']


@pytest.mark.parametrize('bad,code', [
    (response(ORG, []), 'ASSOCIATION_BOUNDARY'),
    (response(TEAM, [{'id': PROJECT}, {'id': PROJECT}]), 'DUPLICATE_IDENTITY'),
    (response(TEAM, [], True, None), 'CURSOR_LOOP'),
    ({'data': {'entity': None}, 'errors': [{'message': 'private error body'}]}, 'GRAPHQL_ERROR'),
])
def test_bad_association_never_reports_success(associations, tmp_path, bad, code):
    source = GraphSource({'Association_team_projects': bad})
    issues = setup_issues(source, tmp_path)
    with pytest.raises(base.SourceError, match=code):
        associations.export_associations(source, issues, tmp_path / 'out')
    saved = (tmp_path / 'out/manifest.json').read_text()
    assert json.loads(saved)['status'] == 'FAILED'
    assert 'private error body' not in saved


def test_foreign_cycle_team_is_rejected_before_page_commit(associations, tmp_path):
    source = GraphSource({'Association_team_cycles': response(TEAM, [{'id': CYCLE, 'team': {'id': ORG}}])})
    with pytest.raises(base.SourceError, match='TEAM_BOUNDARY'):
        associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    pages = list((tmp_path / 'out').glob('page-*.json'))
    assert all(ORG not in p.read_text() for p in pages)


def test_committed_pages_resume_after_auth_loss_without_duplicate_document(associations, tmp_path):
    source = GraphSource({'Association_project_detail': {'errors': [{'message': 'reauth required'}]}})
    issues = setup_issues(source, tmp_path)
    output = tmp_path / 'out'
    with pytest.raises(base.SourceError, match='GRAPHQL_ERROR'):
        associations.export_associations(source, issues, output)
    original = {p.name: p.read_bytes() for p in output.glob('page-*.json')}
    good = Source()
    result = associations.export_associations(good, issues, output, resume=True)
    assert result['counts'].get('document', 0) == 1
    assert all((output / name).read_bytes() == raw for name, raw in original.items())
    assert not any('Association_issue_documents' in q for q, _ in good.calls)


def test_checksum_and_malformed_resume_rejection_preserves_manifest(associations, tmp_path):
    source = Source()
    issues = setup_issues(source, tmp_path)
    output = tmp_path / 'out'
    associations.export_associations(source, issues, output)
    saved = output / 'manifest.json'
    original = saved.read_bytes()
    page = output / 'page-000001.json'
    corrupted = json.loads(page.read_text())
    corrupted['data']['entity']['fields'][0]['name'] = 'tampered_schema_field'
    page.write_text(json.dumps(corrupted))
    with pytest.raises(base.SourceError, match='CHECKSUM_MISMATCH'):
        associations.export_associations(Source(), issues, output, resume=True)
    assert saved.read_bytes() == original
    saved.write_text('[]')
    with pytest.raises(base.SourceError, match='RESUME_SHAPE'):
        associations.export_associations(Source(), issues, output, resume=True)
    assert saved.read_text() == '[]'


def test_verified_seed_and_private_output_are_required(associations, tmp_path):
    source = Source()
    issues = setup_issues(source, tmp_path)
    (issues / 'page-000001.json').write_text('tampered source')
    with pytest.raises(base.SourceError, match='CHECKSUM_MISMATCH'):
        associations.export_associations(source, issues, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_complete_resume_replays_locally_and_does_not_overwrite_new_run(associations, tmp_path):
    source = Source()
    issues = setup_issues(source, tmp_path)
    output = tmp_path / 'out'
    first = associations.export_associations(source, issues, output)
    again = Source()
    second = associations.export_associations(again, issues, output, resume=True)
    assert first['counts'] == second['counts']
    assert len(again.calls) == 1
    assert all(p.stat().st_mode & 0o077 == 0 for p in output.iterdir())
    before = (output / 'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        associations.export_associations(Source(), issues, output)
    assert (output / 'manifest.json').read_bytes() == before


def test_request_and_byte_limits_preserve_resume_boundary(associations, tmp_path):
    source = Source()
    issues = setup_issues(source, tmp_path)
    output = tmp_path / 'out'
    with pytest.raises(base.SourceError, match='REQUEST_LIMIT'):
        associations.export_associations(source, issues, output, max_requests=1)
    assert len(list(output.glob('page-*.json'))) == 1
    result = associations.export_associations(Source(), issues, output, resume=True)
    assert result['counts'].get('document', 0) == 1
    with pytest.raises(base.SourceError, match='EXPORT_BUDGET'):
        associations.export_associations(Source(), issues, tmp_path / 'small', max_bytes=1)
    assert list((tmp_path / 'small').glob('page-*.json')) == []


def test_api_field_inventory_does_not_claim_unread_custom_usage_absent(associations, tmp_path):
    source = Source()
    result = associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    coverage = result['coverage']
    assert coverage['issue_schema_fields'] == ['id', 'projectMilestone']
    assert coverage['source_issue_field_usage']['id'] == {'present': 1, 'populated': 1}
    assert coverage['custom_field_usage']['status'] == 'unavailable_or_unread'
    assert coverage['custom_field_usage']['cutover_disposition_required'] is True


def test_milestone_cannot_claim_a_different_parent_project(associations, tmp_path):
    source = GraphSource({'Association_project_projectMilestones': response(PROJECT, [{'id': MILESTONE, 'project': {'id': FOREIGN_PROJECT}}])})
    with pytest.raises(base.SourceError, match='ASSOCIATION_BOUNDARY'):
        associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')


def test_fixture_m_all_six_issue_document_associations_are_visited_once(associations, tmp_path):
    ids = ['10000000-0000-0000-0000-%012d' % n for n in [2, 5, 11, 17, 21, 30]]
    source = GraphSource({
        'ExportIssues': {'data': {'issues': {'nodes': [{'id': k, 'identifier': 'FAS-%d' % n, 'team': {'id': TEAM}} for k, n in zip(ids, [2,5,11,17,21,30])], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}},
        'Association_issue_documents': lambda v: response(v['id'], [{'id': DOC, 'issue': {'id': ISSUE}, 'content': 'Only reachable via FAS-2'}] if v['id'] == ISSUE else []),
    })
    result = associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    requested = [v['id'] for q, v in source.calls if 'Association_issue_documents' in q]
    assert requested == ids
    assert result['counts'].get('document', 0) == 1
    assert result['edges'] == [['issue', ISSUE, 'documents', 'document', DOC]]


def test_initiative_parent_without_direct_project_is_traversed_once(associations, tmp_path):
    parent = '40000000-0000-0000-0000-000000000002'
    source = GraphSource({
        'Association_project_initiatives': response(PROJECT, [{'id': INITIATIVE, 'parentInitiative': {'id': parent}}]),
        'Association_initiative_detail': lambda v: {'data': {'entity': {'id': v['id'], 'parentInitiative': {'id': parent} if v['id'] == INITIATIVE else None}}},
        'Association_initiative_documents': lambda v: response(v['id'], [{'id': DOC, 'initiative': {'id': parent}, 'title': 'Parent-only doc'}] if v['id'] == parent else []),
    })
    result = associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    assert result['counts']['initiative'] == 2
    assert ['initiative', INITIATIVE, 'parentInitiative', 'initiative', parent] in result['edges']
    assert ['initiative', parent, 'documents', 'document', DOC] in result['edges']
    assert sum('Association_initiative_detail' in q and v['id'] == parent for q, v in source.calls) == 1


def test_standalone_team_document_is_discovered_without_project_or_issue_link(associations, tmp_path):
    standalone = '30000000-0000-0000-0000-000000000009'
    source = GraphSource({'Association_catalog_documents': {'data': {'entity': {'nodes': [{'id': standalone, 'team': {'id': TEAM}, 'title': 'Standalone team doc'}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}})
    result = associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    assert result['counts']['document'] == 2
    assert ['catalog', TEAM, 'documents', 'document', standalone] in result['edges']
    query = next(q for q, _ in source.calls if 'Association_catalog_documents' in q)
    assert 'filter: {team: {id: {eq: $id}}}' in query


def test_team_led_initiative_with_no_project_is_discovered(associations, tmp_path):
    source = GraphSource({
        'Association_catalog_initiatives': {'data': {'entity': {'nodes': [{'id': INITIATIVE, 'leadTeam': {'id': TEAM}}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}},
        'Association_initiative_detail': {'data': {'entity': {'id': INITIATIVE, 'leadTeam': {'id': TEAM}}}},
    })
    result = associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    assert result['counts']['initiative'] == 1
    assert ['catalog', TEAM, 'initiatives', 'initiative', INITIATIVE] in result['edges']


def test_team_catalog_rejects_foreign_document(associations, tmp_path):
    source = GraphSource({'Association_catalog_documents': {'data': {'entity': {'nodes': [{'id': DOC, 'team': {'id': ORG}}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}})
    with pytest.raises(base.SourceError, match='TEAM_BOUNDARY'):
        associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')


def test_foreign_catalog_initiative_is_denied_before_payload_commit_and_traversal(associations, tmp_path):
    source = GraphSource({
        'Association_catalog_initiatives': {'data': {'entity': {'nodes': [{'id': INITIATIVE, 'leadTeam': {'id': ORG}, 'content': 'foreign-private-fixture'}], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}},
        'Association_initiative_detail': {'data': {'entity': {'id': INITIATIVE, 'leadTeam': {'id': ORG}}}},
    })
    with pytest.raises(base.SourceError, match='TEAM_BOUNDARY'):
        associations.export_associations(source, setup_issues(source, tmp_path), tmp_path / 'out')
    assert not any('Association_initiative_' in q for q, _ in source.calls)
    assert all('foreign-private-fixture' not in p.read_text() for p in (tmp_path / 'out').glob('page-*.json'))


def test_cancel_retains_committed_checkpoint_and_corrected_resume(associations, tmp_path):
    def interrupt(_):
        raise KeyboardInterrupt()
    source = GraphSource({'Association_project_detail': interrupt})
    issues = setup_issues(source, tmp_path)
    with pytest.raises(base.SourceError, match='INTERRUPTED'):
        associations.export_associations(source, issues, tmp_path / 'out')
    before = {p.name: p.read_bytes() for p in (tmp_path / 'out').glob('page-*.json')}
    restored = associations.export_associations(Source(), issues, tmp_path / 'out', resume=True)
    assert restored['counts']['document'] == 1
    assert all((tmp_path / 'out' / n).read_bytes() == raw for n, raw in before.items())


def test_concurrent_writer_cannot_rewrite_checkpoint(associations, tmp_path):
    import fcntl
    source = Source()
    issues = setup_issues(source, tmp_path)
    output = tmp_path / 'out'
    associations.export_associations(source, issues, output)
    before = (output / 'manifest.json').read_bytes()
    with (output / '.lock').open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(base.SourceError, match='EXPORT_LOCKED'):
            associations.export_associations(Source(), issues, output, resume=True)
    assert (output / 'manifest.json').read_bytes() == before
