"""Independent raw issue/graph readback; no production exporter imports or network."""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    assert not path.is_symlink() and path.stat().st_mode & 0o077 == 0
    return json.loads(path.read_bytes())


def issues(directory):
    manifest = load(directory / 'manifest.json')
    assert manifest['status'] == 'COMPLETE_FOR_ISSUES'
    records = {}
    for page in manifest['pages']:
        path = directory / page['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == page['sha256']
        for row in load(path)['data']['issues']['nodes']:
            assert row['id'] not in records
            records[row['id']] = row
    assert len(records) == manifest['issue_count']
    return records


def fields(value, path=()):
    if isinstance(value, dict) and value:
        for name in sorted(value):
            yield from fields(value[name], path + (name,))
    else:
        yield '.'.join(s.replace('\\', '\\\\').replace('.', '\\.') for s in path), value


def verify(before_issues, after_issues, before_graph, after_graph, report):
    for directory in [before_issues, after_issues, before_graph, after_graph, report]:
        assert not directory.is_symlink() and directory.stat().st_mode & 0o077 == 0
    left, right = issues(before_issues), issues(after_issues)
    result = load(report / 'manifest.json')
    changes = set()
    for key in left.keys() & right.keys():
        old, new = dict(fields(left[key])), dict(fields(right[key]))
        changes.update((key,f) for f in old.keys() | new.keys() if (f in old)!=(f in new) or old.get(f)!=new.get(f))
    assert changes == {(r['id'],r['field']) for r in result['delta']['modified_fields'] if r['kind']=='issue'}
    assert right.keys()-left.keys() == {r['id'] for r in result['delta']['added_entities'] if r['kind']=='issue'}
    assert left.keys()-right.keys() == {r['id'] for r in result['delta']['tombstone_candidates'] if r['kind']=='issue'}
    old_graph, new_graph = load(before_graph / 'manifest.json'), load(after_graph / 'manifest.json')
    old_edges, new_edges = {tuple(e) for e in old_graph['edges']}, {tuple(e) for e in new_graph['edges']}
    assert new_edges-old_edges == {tuple(e) for e in result['delta']['added_edges']}
    assert old_edges-new_edges == {tuple(e) for e in result['delta']['removed_edges']}
    rows = {(r['kind'],r['field']):r for r in result['coverage']}
    assert rows['issue','title']['field_present'] == len(right)
    assert all(not r['native_verified'] for r in rows.values())
    assert result['cutoff']['verified'] is False and result['readiness']['cutover_ready'] is False
    assert result['comparison']['equal'] == (not any(result['delta'].values()))
    assert result['comparison']['exit_code'] == (0 if result['comparison']['equal'] else 1)
    return {'status':'PASS','issue_field_changes':len(changes),'issue_rows':len(right),
            'issue_diffs_match_raw_pages':True,'edge_diffs_match_verified_graphs':True,
            'private_modes_verified':True,'cutover_ready':False,
            'scope':'Issue field/row diffs and all graph edge diffs; association hashes/counts separately verified'}


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Run verification without Python optimization')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['before-issues','after-issues','before-graph','after-graph','report']:
        parser.add_argument('--'+name,required=True,type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.before_issues,args.after_issues,args.before_graph,args.after_graph,args.report)))
    except (AssertionError,OSError,ValueError,KeyError,TypeError):
        raise SystemExit('Comparison readback failed; private payloads omitted')
