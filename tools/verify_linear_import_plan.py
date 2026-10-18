#!/usr/bin/env python3
"""Independent no-network receipt check against archived source pages and DB snapshots."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(issues, output):
    if not __debug__:raise ValueError("OPTIMIZATION_NOT_SUPPORTED")
    issues,output=Path(issues),Path(output)
    report=json.loads((output/'manifest.json').read_bytes())
    source=json.loads((issues/'manifest.json').read_bytes())
    expected={}
    for page in source['pages']:
        raw=(issues/page['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==page['sha256'],'source checksum'
        for row in json.loads(raw)['data']['issues']['nodes']:
            assert row['id'] not in expected,'duplicate source'
            expected[row['id']]=row
    mapped={r['source_uuid']:r for r in report['mapping'] if r['source_kind']=='issue'}
    assert set(mapped)==set(expected),'missing/extra issue'
    assert len(mapped)==report['counts']['issue']==source['issue_count'],'issue count'
    projects={r['source_uuid']:r for r in report['mapping'] if r['source_kind']=='project'}
    for key,row in expected.items():
        actual=mapped[key]
        assert actual['source_identifier']==row['identifier'],'display identity'
        assert actual['sequence_id']==int(row['identifier'].split('-')[1]),'number changed'
        module=(row.get('project') or {}).get('id')
        assert actual['source_project_uuid']==module,'source module'
        assert actual['module_uuid']==(projects[module]['destination_uuid'] if module else None),'module placement'
        assert actual['project_uuid']==report['target']['project_uuid'],'FAS scope'
    snapshots=[]
    for name in ['before','after']:
        raw=(output/('destination-'+name+'.json')).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==report['destination_'+name],'snapshot digest'
        value=json.loads(raw);assert value['read_only'] is True,'read-only assertion'
        snapshots.append(value)
    equal=snapshots[0]==snapshots[1]
    assert equal==report['destination_unchanged'],'destination comparison'
    assert report['can_import'] is False and report['destination_writes']==0,'import gate'
    return {'verified_issue_count':len(mapped),'destination_unchanged':equal,
            'tables_compared':len(snapshots[0]['tables']),'can_import':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issues',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:print(json.dumps(verify(args.issues,args.output)))
    except (AssertionError,KeyError,ValueError,OSError,TypeError):
        print(json.dumps({'code':'RECEIPT_VERIFICATION_FAILED'}));raise SystemExit(1)
