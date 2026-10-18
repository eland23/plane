"""Independent offline check of original actor payloads and source issue references."""
import argparse
import hashlib
import json
from pathlib import Path


def require(condition):
    if not condition:
        raise ValueError('ACTOR_RECEIPT_MISMATCH')


def verify(issues, actors):
    issues,actors=Path(issues),Path(actors)
    source=json.loads((issues/'manifest.json').read_bytes())
    manifest=json.loads((actors/'manifest.json').read_bytes())
    require(manifest['status']=='COMPLETE_FOR_REFERENCED_ACTORS')
    require(manifest['organization_id']==source['organization_id'] and manifest['team_id']==source['team_id'])
    require(manifest['accounts_created']==0 and manifest['invitations_sent']==0)
    archived={}
    for entry in manifest['actors']:
        require(entry['status']=='ARCHIVED' and entry['source_uuid'] not in archived)
        require(Path(entry['file']).name==entry['file'])
        raw=(actors/entry['file']).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==entry['sha256'])
        data=json.loads(raw)['data'];actor=data['user']
        require(data['organization']['id']==source['organization_id']==actor['organization']['id'])
        require(actor['id']==entry['source_uuid'] and type(actor['active']) is bool)
        archived[actor['id']]=actor
    counts={'creator':0,'assignee':0}
    for page in source['pages']:
        raw=(issues/page['file']).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==page['sha256'])
        for issue in json.loads(raw)['data']['issues']['nodes']:
            for field in counts:
                key=(issue.get(field) or {}).get('id')
                if key:
                    require(key in archived)
                    counts[field]+=1
    require(manifest['counts']=={'archived':len(archived),'blocked':0})
    return {'archived_actors':len(archived),'inactive_actors':sum(not a['active'] for a in archived.values()),
            'verified_issue_references':counts,'accounts_created':0,'invitations_sent':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issues',required=True);parser.add_argument('--actors',required=True)
    args=parser.parse_args()
    try:print(json.dumps(verify(args.issues,args.actors)))
    except (OSError,ValueError,KeyError,TypeError):
        print(json.dumps({'code':'ACTOR_RECEIPT_VERIFICATION_FAILED'}));raise SystemExit(1)
