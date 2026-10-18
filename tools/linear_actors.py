"""Preserve referenced Linear actors without creating accounts or invitations."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from linear_export import LinearHTTP, SourceError, graphql, identity, manifest_file, outside_git, private_file
from linear_associations import read_private
from linear_coverage import read_bundle, leaves

ACTOR_QUERY = '''query ExportActor($id: String!) {
 organization { id }
 user(id: $id) { id name displayName email active createdAt updatedAt archivedAt organization { id } }
}'''
PROFILE = hashlib.sha256(Path(__file__).read_bytes() + ACTOR_QUERY.encode()).hexdigest()
ACTOR_FIELDS = {'creator', 'assignee', 'owner', 'lead', 'updatedBy', 'user'}


def referenced_actors(bundle):
    result = {key for kind, key in bundle['entities'] if kind == 'user'}
    for record in bundle['entities'].values():
        for field, value in record.items():
            parts = field.split('.')
            if len(parts) >= 2 and parts[-1] == 'id' and parts[-2] in ACTOR_FIELDS and value:
                result.add(identity(value))
    if len(result) > 10000:
        raise SourceError('ACTOR_BUDGET')
    return sorted(result)


def checked_actor(data, key, organization):
    if identity(data['organization']['id']) != organization:
        raise SourceError('ACTOR_SCOPE')
    actor = data['user']
    if actor is None:
        return None
    if identity(actor['id']) != key or identity(actor['organization']['id']) != organization:
        raise SourceError('ACTOR_SCOPE')
    if type(actor.get('active')) is not bool or any(not isinstance(actor.get(f), str) for f in ['name', 'displayName', 'email', 'createdAt', 'updatedAt']):
        raise SourceError('ACTOR_SHAPE')
    return actor


def export_actors(source, issues, associations, destination):
    bundle = read_bundle(issues, associations)
    directory = Path(destination).resolve()
    outside_git(directory)
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    except OSError:
        raise SourceError('ACTOR_OUTPUT_EXISTS_OR_IO') from None
    manifest = {'schema_version': 1, 'source_fingerprint': bundle['fingerprint'],
                'organization_id': bundle['organization_id'], 'team_id': bundle['team_id'],
                'profile': PROFILE, 'status': 'RUNNING', 'actors': [],
                'atomic_snapshot': False, 'accounts_created': 0, 'invitations_sent': 0}
    manifest_file(directory, manifest)
    total = 0
    try:
        for number, key in enumerate(referenced_actors(bundle), 1):
            entry = {'source_uuid': key}
            try:
                data = graphql(source, ACTOR_QUERY, {'id': key})
            except SourceError as error:
                # Provider errors mean unread, never deleted/nonexistent. No raw error body.
                if str(error) not in ['GRAPHQL_ERROR', 'SOURCE_HTTP_401', 'SOURCE_HTTP_403']:
                    raise
                entry.update(status='BLOCKED', code=str(error))
            else:
                actor = checked_actor(data, key, bundle['organization_id'])
                raw = json.dumps({'data': data}, sort_keys=True, ensure_ascii=False).encode()
                total += len(raw)
                if len(raw) > 16*1024*1024 or total > 64*1024*1024:
                    raise SourceError('ACTOR_BUDGET')
                file = 'actor-%06d.json' % number
                private_file(directory/file, raw)
                entry.update(status='ARCHIVED' if actor else 'BLOCKED', file=file,
                             sha256=hashlib.sha256(raw).hexdigest())
                if actor is None:
                    entry['code'] = 'ACTOR_UNAVAILABLE_OR_ACCESS_LOST'
            manifest['actors'].append(entry)
            manifest_file(directory, manifest)
        manifest['counts'] = {'archived': sum(e['status']=='ARCHIVED' for e in manifest['actors']),
                              'blocked': sum(e['status']=='BLOCKED' for e in manifest['actors'])}
        manifest['status'] = 'COMPLETE_WITH_BLOCKED_ACTORS' if manifest['counts']['blocked'] else 'COMPLETE_FOR_REFERENCED_ACTORS'
        manifest_file(directory, manifest)
        return manifest
    except (SourceError, OSError, KeyError, ValueError, TypeError, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, SourceError) else ('CANCELLED' if isinstance(error, KeyboardInterrupt) else 'ACTOR_INPUT_OR_IO')
        manifest.update(status='FAILED', failure_code=code)
        manifest_file(directory, manifest)
        raise SourceError(code) from None


def read_actors(directory, bundle):
    directory = Path(directory).resolve()
    outside_git(directory)
    try:
        if directory.stat().st_mode & 0o077:
            raise SourceError('OUTPUT_PERMISSIONS')
        raw = read_private(directory/'manifest.json')
        manifest = json.loads(raw)
        if manifest.get('schema_version') != 1 or manifest.get('profile') != PROFILE or any(manifest.get(k) != bundle[k] for k in ['organization_id', 'team_id']) or manifest.get('source_fingerprint') != bundle['fingerprint']:
            raise SourceError('ACTOR_INPUT_SCOPE')
        if manifest['status'] not in ['COMPLETE_FOR_REFERENCED_ACTORS', 'COMPLETE_WITH_BLOCKED_ACTORS']:
            raise SourceError('INCOMPLETE_ACTOR_INPUT')
        entries = manifest['actors']
        if [entry['source_uuid'] for entry in entries] != referenced_actors(bundle):
            raise SourceError('ACTOR_INPUT_SCOPE')
        result, known, total = {}, set(), 0
        for number, entry in enumerate(entries, 1):
            if entry['status'] not in ['ARCHIVED', 'BLOCKED']:
                raise SourceError('ACTOR_INPUT_SHAPE')
            if 'file' in entry:
                if entry['file'] != 'actor-%06d.json' % number:
                    raise SourceError('ACTOR_INPUT_SHAPE')
                known.add(entry['file'])
                page = read_private(directory/entry['file']);total += len(page)
                if total > 64*1024*1024:
                    raise SourceError('ACTOR_BUDGET')
                if hashlib.sha256(page).hexdigest() != entry['sha256']:
                    raise SourceError('ACTOR_CHECKSUM')
                actor = checked_actor(json.loads(page)['data'], entry['source_uuid'], bundle['organization_id'])
                if actor is not None:
                    if entry['status'] != 'ARCHIVED':
                        raise SourceError('ACTOR_INPUT_SHAPE')
                    result[entry['source_uuid']] = leaves(actor)
                elif entry['status'] != 'BLOCKED' or entry.get('code') != 'ACTOR_UNAVAILABLE_OR_ACCESS_LOST':
                    raise SourceError('ACTOR_INPUT_SHAPE')
            elif entry['status'] != 'BLOCKED' or entry.get('code') not in ['GRAPHQL_ERROR', 'SOURCE_HTTP_401', 'SOURCE_HTTP_403']:
                raise SourceError('ACTOR_INPUT_SHAPE')
        if any(p.name not in known for p in directory.glob('actor-*.json')):
            raise SourceError('ACTOR_ORPHAN_PAGE')
        counts = {'archived': len(result), 'blocked': len(entries)-len(result)}
        if counts != manifest['counts'] or (manifest['status']=='COMPLETE_FOR_REFERENCED_ACTORS') != (counts['blocked']==0):
            raise SourceError('ACTOR_INPUT_SHAPE')
        return result, hashlib.sha256(raw).hexdigest()
    except (OSError, KeyError, ValueError, TypeError, AttributeError):
        raise SourceError('ACTOR_INPUT_OR_IO') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ['issues', 'associations', 'output']:
        parser.add_argument('--'+field, required=True)
    args = parser.parse_args()
    try:
        result = export_actors(LinearHTTP(os.environ.get('LINEAR_API_KEY')), args.issues, args.associations, args.output)
        print(json.dumps({'status': result['status'], 'counts': result['counts']}))
        return 1 if result['counts']['blocked'] else 0
    except SourceError as error:
        print(json.dumps({'code': str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
