"""Independent private asset-page/blob readback; no production imports or network."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit


def private(path):
    assert not path.is_symlink() and path.stat().st_mode & 0o077 == 0


def load(path):
    private(path)
    return json.loads(path.read_bytes())


def sha(path):
    private(path)
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''):checksum.update(chunk)
    return checksum.hexdigest()


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for child in value.values():yield from strings(child)
    elif isinstance(value,list):
        for child in value:yield from strings(child)


def verify(directory, issues, associations):
    for path in [directory,issues,associations]:private(path)
    manifest=load(directory/'manifest.json')
    assert manifest['status'] in ['COMPLETE_FOR_DISCOVERED_ASSETS','COMPLETE_WITH_BLOCKED_ASSETS']
    fingerprint=hashlib.sha256(json.dumps([sha(issues/'manifest.json'),sha(associations/'manifest.json')],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    assert manifest['source_fingerprint']==fingerprint
    source=load(issues/'manifest.json');ids=set();source_text=[]
    for page in source['pages']:
        assert sha(issues/page['file'])==page['sha256']
        data=load(issues/page['file'])
        ids.update(n['id'] for n in data['data']['issues']['nodes']);source_text.extend(strings(data))
    assert len(ids)==source['issue_count']
    graph=load(associations/'manifest.json')
    for page in graph['pages']:
        assert sha(associations/page['file'])==page['sha256']
        source_text.extend(strings(load(associations/page['file'])))
    ids=sorted(ids);index=0;cursor=None;seen=set();cursors=set();attachment_urls=[]
    for number,page in enumerate(manifest['pages'],1):
        assert page['file']=='page-%06d.json'%number and index<len(ids)
        assert page['issue']==ids[index] and page['cursor']==cursor
        assert sha(directory/page['file'])==page['sha256']
        data=load(directory/page['file']);source_text.extend(strings(data));issue=data['data']['issue']
        assert issue['id']==ids[index] and issue['team']['id']==manifest['team_id']
        for node in issue['attachments']['nodes']:
            assert node['id'] not in seen
            assert node['issue']['id']==ids[index] and node['issue']['team']['id']==manifest['team_id']
            seen.add(node['id']);attachment_urls.append((node['id'],node['url']))
        info=issue['attachments']['pageInfo']
        assert type(info['hasNextPage']) is bool
        if info['hasNextPage']:
            assert info['endCursor'] and (index,info['endCursor']) not in cursors
            cursors.add((index,info['endCursor']));cursor=info['endCursor']
        else:index+=1;cursor=None
    assert index==len(ids)
    keys=set();archived=blocked=0;files=set()
    for entry in manifest['assets']:
        assert entry['key']==hashlib.sha256(entry['url'].encode()).hexdigest() and entry['key'] not in keys
        keys.add(entry['key'])
        assert entry['owners'] and any(entry['url'] in text for text in source_text)
        if entry['status']=='ARCHIVED':
            parsed=urlsplit(entry['url']);assert parsed.scheme=='https' and parsed.netloc.lower()=='uploads.linear.app'
            assert entry['file']=='sha256-'+entry['sha256']
            assert sha(directory/entry['file'])==entry['sha256']
            assert (directory/entry['file']).stat().st_size==entry['size']
            assert entry['reference']=='asset:sha256:'+entry['sha256']
            files.add(entry['file']);archived+=1
        else:
            assert entry['status']=='BLOCKED' and entry['code']=='ASSET_URL_DENIED';blocked+=1
    assert all(r['disposition']=='reference_link' for r in manifest['references'])
    for key,url in attachment_urls:
        owner=['attachment',key,'url']
        parsed=urlsplit(url)
        if parsed.scheme=='https' and parsed.netloc.lower()=='uploads.linear.app':
            assert any(e['url']==url and owner in e['owners'] for e in manifest['assets'])
        else:
            assert any(r['url']==url and r['owner']==owner for r in manifest['references'])
    assert not list(directory.glob('.part-*'))
    for path in directory.iterdir():private(path)
    return {'status':'PASS','issue_scopes':len(ids),'attachment_pages':len(manifest['pages']),
            'attachment_records':len(seen),'asset_candidates':len(keys),'archived':archived,'blocked':blocked,
            'unique_blobs':len(files),'reference_links':len(manifest['references']),
            'all_page_hashes_and_terminal_scopes_verified':True,'blob_hashes_sizes_private_modes_verified':True,
            'source_bindings_verified':True,'partial_files_absent':True,'full_migration_backup':False,
            'started_at':manifest['started_at'],'finished_at':manifest['finished_at']}


if __name__=='__main__':
    if not __debug__:raise SystemExit('Run verification without Python optimization')
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['archive','issues','associations']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(verify(args.archive,args.issues,args.associations),sort_keys=True))
    except (AssertionError,OSError,ValueError,KeyError,TypeError):raise SystemExit('Asset readback failed; private payloads omitted')
