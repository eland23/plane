"""Independent readback of private page hashes, connection provenance and graph totals."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def verify(directory):
    directory = Path(directory)
    assert directory.stat().st_mode & 0o077 == 0
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['status'] == 'COMPLETE_FOR_ASSOCIATIONS'
    counts, edges, cursors, complete, archived = defaultdict(set), set(), {}, set(), defaultdict(set)
    for index, record in enumerate(manifest['pages'], 1):
        assert record['file'] == 'page-%06d.json' % index
        file = directory / record['file']
        assert not file.is_symlink() and file.stat().st_mode & 0o077 == 0
        raw = file.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record['sha256']
        entity = json.loads(raw)['data']['entity']
        parent, key, field, kind = record['job']
        job = tuple(record['job'])
        assert job not in complete and record['cursor'] == cursors.get(job)
        if parent == 'schema':
            assert entity['name'] == 'Issue'
            complete.add(job)
            continue
        if field == 'detail':
            assert entity['id'] == key
            nodes = [entity]
            complete.add(job)
        else:
            if parent == 'catalog':
                connection = entity
            else:
                assert entity['id'] == key
                connection = entity['connection']
            nodes = connection['nodes']
            info = connection['pageInfo']
            if info['hasNextPage']:
                assert info['endCursor'] and info['endCursor'] != cursors.get(job)
                cursors[job] = info['endCursor']
            else:
                complete.add(job)
        for node in nodes:
            counts[kind].add(node['id'])
            if node.get('archivedAt') is not None:
                archived[kind].add(node['id'])
            if field != 'detail':
                edges.add((parent, key, field, kind, node['id']))
            if kind == 'initiative' and node.get('parentInitiative'):
                edges.add(('initiative', node['id'], 'parentInitiative', 'initiative', node['parentInitiative']['id']))
    assert all(job in complete for job in cursors)
    assert {k: len(v) for k, v in counts.items()} == manifest['counts']
    assert [list(e) for e in sorted(edges)] == manifest['edges']
    assert all(not f.is_symlink() and f.stat().st_mode & 0o077 == 0 for f in directory.iterdir())
    return {'status': 'PASS', 'counts': manifest['counts'], 'pages': len(manifest['pages']),
            'edges': len(edges), 'archived_by_kind': {k: len(v) for k, v in archived.items()},
            'all_page_checksums_valid': True, 'all_connections_terminal': True,
            'graph_counts_and_edges_match_raw_pages': True, 'private_modes_verified': True,
            'atomic_snapshot': False, 'full_migration_backup': False,
            'export_started_at': manifest['export_started_at'], 'export_finished_at': manifest['export_finished_at']}


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Run verification without Python optimization')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.archive), sort_keys=True))
    except (AssertionError, OSError, KeyError, ValueError, TypeError):
        raise SystemExit('Archive readback failed; private payloads omitted')
