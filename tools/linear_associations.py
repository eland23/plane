"""Read-only association export from a verified Linear issue archive."""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from linear_export import (LinearHTTP, QUERY_HASH as ISSUE_HASH, SCOPE_QUERY, SourceError,
                           checkpoint_shape, connection, graphql, identity,
                           manifest_file, outside_git, private_file)

TIMES = 'createdAt updatedAt archivedAt'
USER = 'id name email active'
FIELDS = {
    'team': 'id name key timezone cyclesEnabled issueEstimationType ' + TIMES,
    'project': 'id name description content identifier startDate targetDate priority sortOrder ' + TIMES + ' status { id name } lead { id name }',
    'initiative': 'id name description content status targetDate sortOrder ' + TIMES + ' owner { id name } leadTeam { id } parentInitiative { id }',
    'cycle': 'id name number description startsAt endsAt completedAt ' + TIMES + ' team { id }',
    'label': 'id name description color isGroup groupType ' + TIMES + ' parent { id } team { id }',
    'state': 'id name description color type position ' + TIMES + ' team { id }',
    'membership': 'id owner ' + TIMES + ' team { id } user { ' + USER + ' }',
    'user': USER,
    'document': 'id title content url sortOrder ' + TIMES + ' creator { id name } updatedBy { id name } parentDocument { id } project { id } initiative { id } issue { id } cycle { id } team { id }',
    'milestone': 'id name description targetDate sortOrder ' + TIMES + ' project { id }',
    'projectUpdate': 'id body bodyData health diff diffMarkdown reactionData ' + TIMES + ' project { id } user { id name }',
    'initiativeUpdate': 'id body bodyData health diff diffMarkdown reactionData ' + TIMES + ' initiative { id } user { id name }',
    'project_reference': 'id',
    'team_reference': 'id',
}
# Only these static fields/endpoints can receive source-derived UUID variables.
ROOTS = {'team': 'team', 'project': 'project', 'initiative': 'initiative', 'cycle': 'cycle', 'label': 'issueLabel', 'issue': 'issue'}
LINKS = {
    'team': [('projects', 'project'), ('cycles', 'cycle'), ('labels', 'label'), ('states', 'state'), ('memberships', 'membership')],
    'project': [('teams', 'team_reference'), ('initiatives', 'initiative'), ('documents', 'document'), ('projectMilestones', 'milestone'), ('projectUpdates', 'projectUpdate'), ('members', 'user')],
    'initiative': [('projects', 'project_reference'), ('documents', 'document'), ('initiativeUpdates', 'initiativeUpdate')],
    'cycle': [('documents', 'document')],
    'label': [('children', 'label')],
    'issue': [('documents', 'document')],
}
QUERY_HASH = hashlib.sha256(Path(__file__).read_bytes() + ISSUE_HASH.encode()).hexdigest()


def read_private(file):
    if file.is_symlink() or file.stat().st_mode & 0o077:
        raise SourceError('OUTPUT_PERMISSIONS')
    if file.stat().st_size > 16 * 1024 * 1024:
        raise SourceError('RESPONSE_TOO_LARGE')
    return file.read_bytes()


def issue_seed(directory):
    directory = Path(directory).resolve()
    outside_git(directory)
    if directory.stat().st_mode & 0o077:
        raise SourceError('OUTPUT_PERMISSIONS')
    raw = read_private(directory / 'manifest.json')
    manifest = checkpoint_shape(json.loads(raw))
    if manifest['query_sha256'] != ISSUE_HASH or manifest['status'] != 'COMPLETE_FOR_ISSUES':
        raise SourceError('ISSUE_ARCHIVE_REQUIRED')
    team = identity(manifest['team_id'])
    seen, cursors, nodes = set(), set(), []
    more, cursor = True, None
    if not manifest['pages']:
        raise SourceError('ISSUE_ARCHIVE_REQUIRED')
    for index, record in enumerate(manifest['pages'], 1):
        payload = read_private(directory / record['file'])
        if hashlib.sha256(payload).hexdigest() != record['sha256']:
            raise SourceError('CHECKSUM_MISMATCH')
        batch, cursor, more = connection(json.loads(payload)['data'], team, seen, cursors)
        if len(batch) != record['issue_count'] or (not more and index != len(manifest['pages'])):
            raise SourceError('RESUME_SHAPE')
        nodes.extend(batch)
    if more or cursor != manifest['next_cursor'] or len(seen) != manifest['issue_count']:
        raise SourceError('ISSUE_ARCHIVE_REQUIRED')
    return manifest, nodes, hashlib.sha256(raw).hexdigest()


class Traversal:
    """Replay committed provider pages to reconstruct the deterministic work queue."""
    def __init__(self, team, issues):
        self.team, self.jobs, self.scheduled = team, [], set()
        self.entities, self.edges, self.schema_fields = {}, set(), []
        self.enqueue(('schema', 'Issue', 'fields', 'schema'))
        self.job_index, self.cursor = 0, None
        self.seen, self.cursors = set(), set()
        self.add('team', team)
        self.enqueue(('catalog', team, 'documents', 'document'))
        self.enqueue(('catalog', team, 'initiatives', 'initiative'))
        for node in sorted(issues, key=lambda n: n['id']):
            self.add('issue', node['id'], detail=False)
            for field, kind in [('project', 'project'), ('cycle', 'cycle')]:
                if node.get(field):
                    self.add(kind, node[field]['id'])
            for label in (node.get('labels') or {}).get('nodes', []):
                self.add('label', label['id'])

    def enqueue(self, job):
        if job not in self.scheduled:
            self.scheduled.add(job)
            self.jobs.append(job)

    def add(self, kind, key, detail=True):
        key = identity(key)
        if detail:
            self.enqueue((kind, key, 'detail', kind))
        for field, child in LINKS.get(kind, []):
            self.enqueue((kind, key, field, child))

    def query(self):
        kind, key, field, child = self.jobs[self.job_index]
        if kind == 'schema':
            return 'query Association_schema { entity: __type(name: "Issue") { name fields(includeDeprecated: true) { name } } }', {}
        if kind == 'catalog':
            condition = '{team: {id: {eq: $id}}}' if field == 'documents' else '{leadTeam: {id: {eq: $id}}}'
            return ('query Association_catalog_%s($id: ID!, $cursor: String) { entity: %s(first: 50, after: $cursor, includeArchived: true, filter: %s) { nodes { %s } pageInfo { hasNextPage endCursor } } }' % (field, field, condition, FIELDS[child])), {'id': key, 'cursor': self.cursor}
        if field == 'detail':
            return 'query Association_%s_detail($id: String!) { entity: %s(id: $id) { %s } }' % (kind, ROOTS[kind], FIELDS[kind]), {'id': key}
        extra = ', includeDisabled: true' if kind == 'project' and field == 'members' else ''
        query = ('query Association_%s_%s($id: String!, $cursor: String) { entity: %s(id: $id) { id '
                 'connection: %s(first: 50, after: $cursor, includeArchived: true%s) { '
                 'nodes { %s } pageInfo { hasNextPage endCursor } } } }') % (kind, field, ROOTS[kind], field, extra, FIELDS[child])
        return query, {'id': key, 'cursor': self.cursor}

    def consume(self, data):
        kind, key, field, child = self.jobs[self.job_index]
        try:
            entity = data['entity']
            if kind == 'schema':
                fields = entity['fields']
                if entity['name'] != 'Issue' or not isinstance(fields, list) or not fields:
                    raise SourceError('SOURCE_SHAPE')
                names = [f['name'] for f in fields]
                if any(not isinstance(n, str) or not n or len(n) > 256 for n in names) or len(names) != len(set(names)):
                    raise SourceError('SOURCE_SHAPE')
                self.schema_fields = sorted(names)
                self.job_index += 1
                return
            if kind == 'catalog':
                entity = {'id': key, 'connection': entity}
            if identity(entity['id']) != key:
                raise SourceError('ASSOCIATION_BOUNDARY')
            if field == 'detail':
                nodes, more, cursor = [entity], False, None
            else:
                page = entity['connection']
                nodes, info = page['nodes'], page['pageInfo']
                more, cursor = info['hasNextPage'], info['endCursor']
                if not isinstance(nodes, list) or type(more) is not bool:
                    raise SourceError('SOURCE_SHAPE')
                if more and (not isinstance(cursor, str) or not cursor or len(cursor) > 4096 or cursor in self.cursors):
                    raise SourceError('CURSOR_LOOP')
            for node in nodes:
                node_id = identity(node['id'])
                if node_id in self.seen:
                    raise SourceError('DUPLICATE_IDENTITY')
                self.seen.add(node_id)
                parent = node.get(kind)
                if child in ('document', 'milestone', 'projectUpdate', 'initiativeUpdate') and isinstance(parent, dict) and identity(parent['id']) != key:
                    raise SourceError('ASSOCIATION_BOUNDARY')
                if kind == 'catalog' and child == 'initiative':
                    lead = node.get('leadTeam')
                    if not lead or identity(lead['id']) != self.team:
                        raise SourceError('TEAM_BOUNDARY')
                scoped_team = node.get('team')
                if kind == 'catalog' and child == 'document' and (not scoped_team or identity(scoped_team['id']) != self.team):
                    raise SourceError('TEAM_BOUNDARY')
                if child in ('cycle', 'state', 'membership') and (not scoped_team or identity(scoped_team['id']) != self.team):
                    raise SourceError('TEAM_BOUNDARY')
                if child in ('label', 'document') and scoped_team and identity(scoped_team['id']) != self.team:
                    raise SourceError('TEAM_BOUNDARY')
                self.entities.setdefault(child, {})[node_id] = node
                if field != 'detail':
                    self.edges.add((kind, key, field, child, node_id))
                if child in ('project', 'initiative', 'cycle', 'label'):
                    self.add(child, node_id)
                if child == 'label' and node.get('parent'):
                    self.add('label', node['parent']['id'])
                if child == 'initiative' and node.get('parentInitiative'):
                    parent_id = identity(node['parentInitiative']['id'])
                    self.edges.add(('initiative', node_id, 'parentInitiative', 'initiative', parent_id))
                    self.add('initiative', parent_id)
            if more:
                self.cursors.add(cursor)
                self.cursor = cursor
            else:
                self.job_index += 1
                self.cursor = None
                self.seen, self.cursors = set(), set()
        except (KeyError, TypeError, AttributeError, ValueError):
            raise SourceError('SOURCE_SHAPE') from None


def export_associations(source, issues, destination, resume=False, max_requests=20000, max_bytes=512 * 1024 * 1024):
    if type(max_requests) is not int or max_requests < 1 or type(max_bytes) is not int or max_bytes < 1:
        raise SourceError('EXPORT_BUDGET')
    seed, nodes, seed_hash = issue_seed(issues)
    directory = Path(destination).resolve()
    outside_git(directory)
    scope = graphql(source, SCOPE_QUERY, {'team': seed['team_id']})
    try:
        if scope['organization']['id'] != seed['organization_id'] or scope['team']['id'] != seed['team_id']:
            raise SourceError('RESUME_SCOPE')
    except (KeyError, TypeError, AttributeError):
        raise SourceError('SOURCE_SHAPE') from None
    if not resume:
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    if not directory.is_dir() or directory.stat().st_mode & 0o077:
        raise SourceError('OUTPUT_PERMISSIONS')
    lock = os.open(str(directory / '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    writable, manifest = False, None
    graph = Traversal(seed['team_id'], nodes)
    total_bytes = 0
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SourceError('EXPORT_LOCKED') from None
        if resume:
            manifest = json.loads(read_private(directory / 'manifest.json'))
            if not isinstance(manifest, dict) or manifest.get('schema_version') != 1 or not isinstance(manifest.get('pages'), list):
                raise SourceError('RESUME_SHAPE')
            if (manifest.get('query_sha256') != QUERY_HASH or manifest.get('issue_manifest_sha256') != seed_hash or
                    manifest.get('team_id') != seed['team_id'] or manifest.get('organization_id') != seed['organization_id']):
                raise SourceError('RESUME_SCOPE')
            for index, record in enumerate(manifest['pages'], 1):
                if not isinstance(record, dict) or record.get('file') != 'page-%06d.json' % index or graph.job_index >= len(graph.jobs):
                    raise SourceError('RESUME_SHAPE')
                if record.get('job') != list(graph.jobs[graph.job_index]) or record.get('cursor') != graph.cursor:
                    raise SourceError('RESUME_SHAPE')
                raw = read_private(directory / record['file'])
                if hashlib.sha256(raw).hexdigest() != record.get('sha256'):
                    raise SourceError('CHECKSUM_MISMATCH')
                graph.consume(json.loads(raw)['data'])
                total_bytes += len(raw)
            if total_bytes > max_bytes:
                raise SourceError('EXPORT_BUDGET')
            known = {r['file'] for r in manifest['pages']}
            if any(p.name not in known for p in directory.glob('page-*.json')):
                raise SourceError('ORPHAN_PAGE')
        else:
            manifest = {'schema_version': 1, 'query_sha256': QUERY_HASH, 'issue_manifest_sha256': seed_hash,
                        'team_id': seed['team_id'], 'organization_id': seed['organization_id'], 'pages': [],
                        'status': 'RUNNING', 'atomic_snapshot': False, 'full_migration_backup': False,
                        'export_started_at': datetime.now(timezone.utc).isoformat()}
        writable = True
        manifest_file(directory, manifest)
        while graph.job_index < len(graph.jobs):
            if len(manifest['pages']) >= max_requests:
                raise SourceError('REQUEST_LIMIT')
            job, cursor = graph.jobs[graph.job_index], graph.cursor
            query, variables = graph.query()
            data = graphql(source, query, variables)
            graph.consume(data)
            raw = (json.dumps({'data': data}, ensure_ascii=False, sort_keys=True) + '\n').encode()
            if total_bytes + len(raw) > max_bytes or shutil.disk_usage(directory).free < len(raw) + 1024 ** 3:
                raise SourceError('EXPORT_BUDGET')
            file = directory / ('page-%06d.json' % (len(manifest['pages']) + 1))
            private_file(file, raw)
            manifest['pages'].append({'file': file.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'job': list(job), 'cursor': cursor})
            total_bytes += len(raw)
            manifest.update(status='RUNNING')
            manifest.pop('failure_code', None)
            manifest_file(directory, manifest)
        manifest.update(status='COMPLETE_FOR_ASSOCIATIONS', counts={k: len(v) for k, v in graph.entities.items()},
                        edges=[list(edge) for edge in sorted(graph.edges)], export_finished_at=datetime.now(timezone.utc).isoformat(),
                        coverage={'selected_fields': FIELDS, 'unselected_fields': 'not inventoried; HLB-447',
                                  'issue_schema_fields': graph.schema_fields,
                                  'source_issue_field_usage': {field: {'present': sum(field in n for n in nodes), 'populated': sum(n.get(field) is not None for n in nodes)} for field in sorted({f for n in nodes for f in n})},
                                  'custom_field_usage': {'status': 'unavailable_or_unread', 'schema_candidates': [f for f in graph.schema_fields if 'custom' in f.lower() or 'type' in f.lower()], 'cutover_disposition_required': True, 'owner': 'HLB-447'},
                                  'deltas_tombstones': 'not performed; HLB-447', 'asset_bytes': 'not downloaded; HLB-448',
                                  'foreign_initiative_projects': 'UUID stubs only; never traversed',
                                  'document_history_comments': 'not exported; later coverage/import children'})
        manifest_file(directory, manifest)
        return manifest
    except (SourceError, OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, SourceError) else ('INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'EXPORT_IO_OR_SHAPE')
        if writable:
            manifest.update(status='FAILED', failure_code=code)
            manifest_file(directory, manifest)
        raise SourceError(code) from None
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issues', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--max-requests', type=int, default=20000)
    parser.add_argument('--max-bytes', type=int, default=512 * 1024 * 1024)
    args = parser.parse_args()
    try:
        result = export_associations(LinearHTTP(os.environ.get('LINEAR_API_KEY')), args.issues, args.output, args.resume, args.max_requests, args.max_bytes)
        print(json.dumps({'status': result['status'], 'counts': result['counts'], 'pages': len(result['pages'])}))
        return 0
    except (SourceError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        print(json.dumps({'code': str(error) if isinstance(error, SourceError) else ('INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'EXPORT_IO_OR_SHAPE')}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
