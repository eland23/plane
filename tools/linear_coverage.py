"""Produce explicit snapshot-delta and source-field coverage manifests."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from linear_export import LinearHTTP, SCOPE_QUERY, SourceError, graphql, identity, outside_git, manifest_file
from linear_associations import QUERY_HASH as ASSOCIATION_HASH, Traversal, issue_seed, read_private

CATEGORIES = {
    'issue': 'Issue', 'project': 'Project', 'cycle': 'Cycle', 'label': 'IssueLabel',
    'state': 'WorkflowState', 'milestone': 'ProjectMilestone', 'initiative': 'Initiative',
    'projectUpdate': 'ProjectUpdate', 'initiativeUpdate': 'InitiativeUpdate',
    'document': 'Document', 'user': 'User', 'membership': 'TeamMembership', 'team': 'Team',
    'comment': 'Comment', 'thread': 'Comment', 'reaction': 'Reaction', 'issueHistory': 'IssueHistory',
    'projectHistory': 'ProjectHistory', 'initiativeHistory': 'InitiativeHistory',
    'documentHistory': 'DocumentContentHistoryType', 'attachment': 'Attachment',
    'view': 'CustomView', 'template': 'Template', 'subscription': 'NotificationSubscription',
    'favorite': 'Favorite', 'release': 'Release', 'customer': 'Customer',
    'agentMetadata': 'AgentSession', 'integration': 'Integration',
    'sla': 'SlaConfiguration', 'settings': 'Team', 'labelGroup': 'IssueLabel', 'inlineImage': 'Document',
}
SCHEMA_QUERY = '''query CoverageSchema($name: String!) {
  entity: __type(name: $name) { name fields(includeDeprecated: true) { name } }
}'''
BUDGET = 512 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise SourceError('INVALID_TIMESTAMP') from None


def leaves(value, prefix=''):
    if isinstance(value, dict) and value:
        result = {}
        for name, child in value.items():
            escaped = name.replace('\\', '\\\\').replace('.', '\\.')
            result.update(leaves(child, prefix + '.' + escaped if prefix else escaped))
        return result
    return {prefix: value}


def read_bundle(issues, associations):
    seed, issue_nodes, seed_hash = issue_seed(issues)
    directory = Path(associations).resolve()
    outside_git(directory)
    if directory.stat().st_mode & 0o077:
        raise SourceError('OUTPUT_PERMISSIONS')
    raw_manifest = read_private(directory / 'manifest.json')
    manifest = json.loads(raw_manifest)
    if not isinstance(manifest, dict) or manifest.get('status') != 'COMPLETE_FOR_ASSOCIATIONS':
        raise SourceError('INCOMPLETE_ASSOCIATION_ARCHIVE')
    if (manifest.get('query_sha256') != ASSOCIATION_HASH or manifest.get('issue_manifest_sha256') != seed_hash or
            manifest.get('team_id') != seed['team_id'] or manifest.get('organization_id') != seed['organization_id']):
        raise SourceError('SNAPSHOT_SCOPE')
    pages = manifest.get('pages')
    if not isinstance(pages, list) or len(pages) > 20000:
        raise SourceError('SNAPSHOT_SHAPE')
    graph = Traversal(seed['team_id'], issue_nodes)
    entities, conflicts = {}, []

    def observe(kind, node):
        key = kind, identity(node['id'])
        record = entities.setdefault(key, {})
        for field, value in node.items():
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', field):
                raise SourceError('SNAPSHOT_SHAPE')
            observed = leaves({field: value})
            previous = {p: v for p, v in record.items() if p == field or p.startswith(field + '.')}
            if previous and previous != observed:
                conflicts.append({'kind': kind, 'id': key[1], 'field': field,
                                  'before_sha256': digest(previous), 'after_sha256': digest(observed)})
            for path in previous:
                del record[path]
            record.update(observed)

    for node in issue_nodes:
        observe('issue', node)
    total = len(raw_manifest)
    for index, record in enumerate(pages, 1):
        if not isinstance(record, dict) or record.get('file') != 'page-%06d.json' % index or graph.job_index >= len(graph.jobs):
            raise SourceError('SNAPSHOT_SHAPE')
        job = graph.jobs[graph.job_index]
        if record.get('job') != list(job) or record.get('cursor') != graph.cursor:
            raise SourceError('SNAPSHOT_PROVENANCE')
        raw = read_private(directory / record['file'])
        total += len(raw)
        if total > BUDGET:
            raise SourceError('SNAPSHOT_BUDGET')
        if hashlib.sha256(raw).hexdigest() != record.get('sha256'):
            raise SourceError('CHECKSUM_MISMATCH')
        data = json.loads(raw)['data']
        graph.consume(data)
        parent, key, field, child = job
        if parent == 'schema':
            continue
        entity = data['entity']
        nodes = [entity] if field == 'detail' else (entity if parent == 'catalog' else entity['connection'])['nodes']
        for node in nodes:
            observe(child, node)
    if graph.job_index != len(graph.jobs) or {k: len(v) for k, v in graph.entities.items()} != manifest.get('counts'):
        raise SourceError('INCOMPLETE_ASSOCIATION_ARCHIVE')
    edges = [list(e) for e in sorted(graph.edges)]
    if edges != manifest.get('edges'):
        raise SourceError('SNAPSHOT_GRAPH_MISMATCH')
    known = {r['file'] for r in pages}
    if any(p.name not in known for p in directory.glob('page-*.json')):
        raise SourceError('ORPHAN_PAGE')
    windows = [seed['export_started_at'], seed['export_finished_at'], manifest['export_started_at'], manifest['export_finished_at']]
    for value in windows:
        instant(value)
    if instant(windows[0]) > instant(windows[1]) or instant(windows[2]) > instant(windows[3]):
        raise SourceError('SNAPSHOT_ORDER')
    return {'organization_id': identity(seed['organization_id']), 'team_id': identity(seed['team_id']),
            'entities': entities, 'edges': {tuple(e) for e in edges}, 'conflicts': conflicts,
            'schema_fields': graph.schema_fields,
            'fingerprint': digest([seed_hash, hashlib.sha256(raw_manifest).hexdigest()]),
            'capture_starts': [windows[0], windows[2]],
            'observation_ids': [digest([seed['organization_id'], seed['team_id'], seed['query_sha256'], windows[0], [p['sha256'] for p in seed['pages']]]),
                                digest([manifest['organization_id'], manifest['team_id'], manifest['query_sha256'], windows[2], [p['sha256'] for p in pages]])],
            'started_at': min(windows, key=instant), 'finished_at': max(windows, key=instant)}


def capture_schema(source, team, destination):
    team = identity(team)
    directory = Path(destination).resolve()
    outside_git(directory)
    scope = graphql(source, SCOPE_QUERY, {'team': team})
    try:
        if identity(scope['team']['id']) != team:
            raise SourceError('SNAPSHOT_SCOPE')
        organization = identity(scope['organization']['id'])
    except (KeyError, TypeError, AttributeError):
        raise SourceError('SOURCE_SHAPE') from None
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    result = {'schema_version': 1, 'status': 'RUNNING', 'organization_id': organization, 'team_id': team,
              'query_sha256': hashlib.sha256(SCHEMA_QUERY.encode()).hexdigest(),
              'types': {}, 'started_at': datetime.now(timezone.utc).isoformat()}
    manifest_file(directory, result)
    cache, authorization_lost = {}, False
    try:
        for kind, name in CATEGORIES.items():
            if name not in cache:
                if authorization_lost:
                    entry = {'type': name, 'status': 'blocked', 'fields': [], 'reason': 'authorization_lost'}
                else:
                    try:
                        data = graphql(source, SCHEMA_QUERY, {'name': name})
                        entity = data['entity']
                        if entity is None:
                            entry = {'type': name, 'status': 'unavailable', 'fields': [], 'reason': 'source_type_not_exposed'}
                        else:
                            names = [field['name'] for field in entity['fields']]
                            if entity['name'] != name or not names or any(not isinstance(f, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,255}', f) for f in names) or len(names) != len(set(names)):
                                raise SourceError('SCHEMA_SHAPE')
                            entry = {'type': name, 'status': 'available', 'fields': sorted(names)}
                    except SourceError as error:
                        if str(error) == 'SCHEMA_SHAPE':
                            raise
                        authorization_lost = str(error) in ('SOURCE_HTTP_401', 'SOURCE_HTTP_403')
                        entry = {'type': name, 'status': 'blocked', 'fields': [], 'reason': str(error)}
                cache[name] = entry
            result['types'][kind] = cache[name]
            manifest_file(directory, result)
        result.update(status='COMPLETE_WITH_BLOCKED_TYPES' if any(e['status'] != 'available' for e in result['types'].values()) else 'COMPLETE',
                      finished_at=datetime.now(timezone.utc).isoformat())
        manifest_file(directory, result)
        return result
    except (SourceError, OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, SourceError) else ('INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'SCHEMA_SHAPE')
        result.update(status='FAILED', failure_code=code)
        manifest_file(directory, result)
        raise SourceError(code) from None


def read_inventory(directory, bundle):
    directory = Path(directory).resolve()
    outside_git(directory)
    if directory.stat().st_mode & 0o077:
        raise SourceError('OUTPUT_PERMISSIONS')
    value = json.loads(read_private(directory / 'manifest.json'))
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('status') not in ('COMPLETE', 'COMPLETE_WITH_BLOCKED_TYPES'):
        raise SourceError('SCHEMA_INVENTORY_REQUIRED')
    if any(value.get(k) != bundle[k] for k in ('organization_id', 'team_id')):
        raise SourceError('SNAPSHOT_SCOPE')
    types = value.get('types')
    if not isinstance(types, dict) or any(k not in CATEGORIES for k in types):
        raise SourceError('SCHEMA_SHAPE')
    for kind, entry in types.items():
        if not isinstance(entry, dict) or entry.get('type') != CATEGORIES[kind] or entry.get('status') not in ('available', 'blocked', 'unavailable'):
            raise SourceError('SCHEMA_SHAPE')
        fields = entry.get('fields', [])
        if not isinstance(fields, list) or len(fields) > 5000 or any(not isinstance(f, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,255}', f) for f in fields) or len(fields) != len(set(fields)):
            raise SourceError('SCHEMA_SHAPE')
    return value


def value_present(value):
    if isinstance(value, dict):
        return any(value_present(v) for k, v in value.items() if k != 'pageInfo')
    if isinstance(value, list):
        return any(value_present(v) for v in value)
    return value is not None and value != ''


def field_ledger(bundle, inventory):
    rows = []
    for kind, source_type in CATEGORIES.items():
        source_kind = {'labelGroup': 'label', 'settings': 'team'}.get(kind, kind)
        records = [r for (k, _), r in bundle['entities'].items() if k == source_kind and (kind != 'labelGroup' or r.get('isGroup') is True)]
        spec = inventory['types'].get(kind, {'status': 'blocked', 'fields': []})
        fields = sorted(set(spec.get('fields', [])) | {f.split('.')[0] for r in records for f in r})
        if not fields:
            fields = ['*']
        for field in fields:
            present = sum(any(f == field or f.startswith(field + '.') for f in r) for r in records)
            populated = sum(any((f == field or f.startswith(field + '.')) and '.pageInfo.' not in f and value_present(v) for f, v in r.items()) for r in records)
            credential = field in {'accessToken', 'refreshToken', 'secret', 'secretKey', 'apiKey', 'password', 'privateKey', 'sessionToken'}
            if credential:
                disposition, reason = 'unsupported', 'credentials_excluded_by_migration_scope'
            elif spec['status'] == 'unavailable':
                disposition, reason = 'unavailable', 'source_type_not_exposed'
            elif spec['status'] == 'blocked':
                disposition, reason = 'blocked', 'schema_access_or_inventory_missing'
            elif field not in spec.get('fields', []):
                disposition, reason = 'unsupported', 'observed_field_not_in_current_schema'
            elif present:
                disposition, reason = 'archive', 'original_observed_payload_preserved'
            else:
                disposition, reason = 'blocked', 'field_not_exported_or_usage_unknown'
            rows.append({'kind': kind, 'source_type': source_type, 'field': field,
                         'disposition': disposition, 'reason': reason, 'records_observed': len(records),
                         'field_present': present, 'field_populated': populated,
                         'usage': 'populated' if populated else ('null_or_empty' if present else 'unknown'),
                         'capture_state': 'partial_object_or_relation' if any(any(f.startswith(field + '.') for f in r) for r in records) else ('observed_value' if present else 'unread'),
                         'native_verified': False, 'owner_disposition_required': not credential, 'owner': 'HLB-447'})
    return rows


def compare_exports(before_issues, before_associations, after_issues, after_associations, schema, destination, cutoff=None):
    try:
        before, after = read_bundle(before_issues, before_associations), read_bundle(after_issues, after_associations)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise SourceError('SNAPSHOT_SHAPE') from None
    if any(before[k] != after[k] for k in ('organization_id', 'team_id')):
        raise SourceError('SNAPSHOT_SCOPE')
    try:
        inventory = read_inventory(schema, after)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise SourceError('SCHEMA_SHAPE') from None
    cutoff = cutoff or after['finished_at']
    requested = instant(cutoff)
    independent = all(left != right for left, right in zip(before['observation_ids'], after['observation_ids']))
    if any(instant(right) < instant(left) for left, right in zip(before['capture_starts'], after['capture_starts'])):
        raise SourceError('SNAPSHOT_ORDER')
    if instant(after['finished_at']) < instant(before['finished_at']):
        raise SourceError('SNAPSHOT_ORDER')
    modified, added, missing = [], [], []
    before_keys, after_keys = set(before['entities']), set(after['entities'])
    for kind, key in sorted(after_keys - before_keys):
        added.append({'kind': kind, 'id': key})
    for kind, key in sorted(before_keys - after_keys):
        missing.append({'kind': kind, 'id': key, 'reason': 'deleted_or_access_lost_or_scope_changed', 'confirmed_deleted': False})
    for kind, key in sorted(before_keys & after_keys):
        left, right = before['entities'][(kind, key)], after['entities'][(kind, key)]
        for field in sorted(set(left) | set(right)):
            if (field in left) != (field in right) or left.get(field) != right.get(field):
                modified.append({'kind': kind, 'id': key, 'field': field, 'before_present': field in left, 'after_present': field in right,
                                 'before_sha256': digest(left[field]) if field in left else None,
                                 'after_sha256': digest(right[field]) if field in right else None})
    removed_edges, added_edges = sorted(before['edges'] - after['edges']), sorted(after['edges'] - before['edges'])
    schema_added = sorted(set(after['schema_fields']) - set(before['schema_fields']))
    schema_removed = sorted(set(before['schema_fields']) - set(after['schema_fields']))
    equal = not (modified or added or missing or removed_edges or added_edges or schema_added or schema_removed)
    ledger = field_ledger(after, inventory)
    exceptions = []
    for (kind, key), record in sorted(after['entities'].items()):
        for field in ('createdAt', 'updatedAt', 'archivedAt', 'completedAt', 'canceledAt', 'startedAt'):
            if record.get(field) and instant(record[field]) > requested:
                exceptions.append({'kind': kind, 'id': key, 'field': field, 'reason': 'observed_event_after_requested_cutoff'})
    report = {'schema_version': 1, 'status': 'COMPLETE_WITH_READINESS_BLOCKERS',
              'organization_id': after['organization_id'], 'team_id': after['team_id'],
              'before_fingerprint': before['fingerprint'], 'after_fingerprint': after['fingerprint'],
              'before_observation_ids': before['observation_ids'], 'after_observation_ids': after['observation_ids'],
              'comparison': {'equal': equal, 'exit_code': 0 if equal else 1, 'independent_observations': independent},
              'delta': {'added_entities': added, 'modified_fields': modified, 'tombstone_candidates': missing,
                        'added_edges': [list(e) for e in added_edges], 'removed_edges': [list(e) for e in removed_edges],
                        'schema_fields_added': schema_added, 'schema_fields_removed': schema_removed},
              'cutoff': {'requested': cutoff, 'verified': False, 'atomic_snapshot': False,
                         'before_window': [before['started_at'], before['finished_at']],
                         'after_window': [after['started_at'], after['finished_at']],
                         'reason': 'read_snapshots_do_not_establish_source_freeze_or_as_of_completeness'},
              'exceptions': exceptions, 'intra_snapshot_conflicts': {'before': before['conflicts'], 'after': after['conflicts']},
              'schema_fingerprint': digest(inventory),
              'schema_comparison': {'scope': 'Issue fields only; prior schemas for other categories unavailable', 'all_types_compared': False},
              'feature_gaps': {name: {'source_type': 'Issue', 'schema_candidates': [f for f in candidates if f in inventory['types'].get('issue', {}).get('fields', [])], 'usage': 'unknown', 'cutover_disposition_required': True, 'owner': 'HLB-447'} for name, candidates in {'custom_properties': ['customFields', 'customProperties'], 'work_item_types': ['type', 'issueType']}.items()},
              'coverage': ledger, 'readiness': {'cutover_ready': False,
                         'blockers': ['owner_field_dispositions_required', 'native_import_evidence_required', 'verified_cutoff_required'] +
                         (['delta_requires_reconciliation'] if not equal else []) +
                         (['intra_snapshot_changes'] if before['conflicts'] or after['conflicts'] else []) +
                         (['cutoff_exceptions'] if exceptions else []) +
                         (['independent_repeat_snapshot_required'] if not independent else [])},
              'generated_at': datetime.now(timezone.utc).isoformat()}
    directory = Path(destination).resolve()
    outside_git(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest_file(directory, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    schema = commands.add_parser('capture-schema')
    schema.add_argument('--team', required=True)
    schema.add_argument('--output', type=Path, required=True)
    compare = commands.add_parser('compare')
    for name in ('before-issues', 'before-associations', 'after-issues', 'after-associations', 'schema', 'output'):
        compare.add_argument('--' + name, type=Path, required=True)
    compare.add_argument('--cutoff')
    args = parser.parse_args()
    try:
        if args.operation == 'capture-schema':
            import os
            result = capture_schema(LinearHTTP(os.environ.get('LINEAR_API_KEY')), args.team, args.output)
            print(json.dumps({'status': result['status'], 'types': len(result['types']),
                              'available_types': sum(t['status'] == 'available' for t in result['types'].values())}))
            return 0 if result['status'] == 'COMPLETE' else 3
        result = compare_exports(args.before_issues, args.before_associations, args.after_issues,
                                 args.after_associations, args.schema, args.output, args.cutoff)
        print(json.dumps({'status': result['status'], 'delta_counts': {k: len(v) for k, v in result['delta'].items()},
                          'coverage_fields': len(result['coverage']), 'cutover_ready': result['readiness']['cutover_ready']}))
        return 1 if not result['comparison']['equal'] else 3
    except (SourceError, OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, SourceError) else ('INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'COVERAGE_INPUT_OR_IO')
        print(json.dumps({'code': code}), file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 2


if __name__ == '__main__':
    sys.exit(main())
