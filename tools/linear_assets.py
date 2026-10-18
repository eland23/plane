"""Archive discovered Linear uploads as private content-addressed bytes."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from linear_export import LinearHTTP, NoRedirect, SCOPE_QUERY, SourceError, graphql, identity, outside_git, manifest_file, private_file
from linear_associations import read_private
from linear_coverage import read_bundle, digest

ATTACHMENTS = '''query AssetAttachments($id: String!, $after: String) {
 issue(id: $id) { id team { id } attachments(first: 100, after: $after, includeArchived: true) {
  nodes { id title url metadata createdAt updatedAt issue { id team { id } } }
  pageInfo { hasNextPage endCursor }
 } }
}'''
PROFILE = hashlib.sha256(ATTACHMENTS.encode()).hexdigest()


def checkpoint(directory, manifest):
    if len(json.dumps(manifest, ensure_ascii=False).encode()) > 16 * 1024 * 1024:
        raise SourceError('ASSET_MANIFEST_BUDGET')
    manifest_file(directory, manifest)


def approved_url(url):
    try:
        if not isinstance(url, str) or len(url) > 8192 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            raise ValueError()
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc.lower() != 'uploads.linear.app' or
                parsed.username or parsed.password or parsed.fragment or not parsed.path.startswith('/') or '\\' in url):
            raise ValueError()
    except (ValueError, TypeError):
        raise SourceError('ASSET_URL_DENIED') from None
    return url


class AssetHTTP:
    def __init__(self, token, opener=None):
        if not token:
            raise SourceError('MISSING_CREDENTIAL')
        self.token = token
        self.opener = opener or build_opener(ProxyHandler({}), NoRedirect())

    def open(self, url):
        approved_url(url)
        try:
            response = self.opener.open(Request(url, headers={'Authorization': self.token, 'Accept-Encoding': 'identity'}), timeout=30)
            if response.status != 200 or response.geturl() != url:
                response.close()
                raise SourceError('ASSET_RESPONSE_DENIED')
            return response
        except HTTPError as error:
            code = error.code
            error.close()
            raise SourceError('ASSET_HTTP_%d' % code) from None
        except (URLError, OSError, ValueError):
            raise SourceError('ASSET_UNAVAILABLE') from None


def blob_hash(path, max_bytes):
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise SourceError('OUTPUT_PERMISSIONS')
    total, checksum = 0, hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            total += len(chunk)
            if total > max_bytes:
                raise SourceError('ASSET_TOO_LARGE')
            checksum.update(chunk)
    return total, checksum.hexdigest()


def attachment_page(data, issue, team):
    try:
        entity = data['issue']
        if identity(entity['id']) != issue or identity(entity['team']['id']) != team:
            raise SourceError('ASSET_SCOPE')
        connection = entity['attachments'];nodes = connection['nodes'];info = connection['pageInfo']
        if not isinstance(nodes, list) or type(info['hasNextPage']) is not bool or (info['hasNextPage'] and not isinstance(info['endCursor'], str)):
            raise SourceError('ASSET_PAGE_SHAPE')
        ids = set()
        for node in nodes:
            key = identity(node['id'])
            if key in ids or not isinstance(node['url'], str):
                raise SourceError('ASSET_PAGE_SHAPE')
            ids.add(key)
            if identity(node['issue']['id']) != issue or identity(node['issue']['team']['id']) != team:
                raise SourceError('ASSET_SCOPE')
        return nodes, info['hasNextPage'], info['endCursor']
    except (KeyError, TypeError, AttributeError):
        raise SourceError('ASSET_PAGE_SHAPE') from None


def discover(bundle, attachments):
    candidates, references = {}, []
    def add(url, owner, required):
        try:
            approved_url(url)
            required = True
        except SourceError:
            if not required:
                references.append({'url': url, 'owner': owner, 'disposition': 'reference_link'})
                return
        key = hashlib.sha256(url.encode()).hexdigest()
        entry = candidates.setdefault(key, {'key': key, 'url': url, 'owners': [], 'status': 'PENDING'})
        if owner not in entry['owners']:
            entry['owners'].append(owner)
    def scan(value, owner):
        if isinstance(value, dict):
            for key, child in value.items():scan(child, owner + [key])
        elif isinstance(value, list):
            for index, child in enumerate(value):scan(child, owner + [str(index)])
        elif isinstance(value, str):
            field = owner[-1].split('.')[-1].lower()
            if field in {'src','imageurl','asseturl','fileurl','downloadurl','thumbnailurl'}:
                add(value, owner, True)
            images = set(re.findall(r'!\[[^\]]*\]\(([^\s)]+)', value))
            images.update(re.findall(r'<img\b[^>]*?\bsrc=[\"\']([^\"\']+)', value, re.IGNORECASE))
            for url in images:add(url, owner, True)
            for url in re.findall(r'https?://[^\s<>"\[\]{}()]+', value):
                url = url.rstrip('.,;')
                if url not in images:
                    field = owner[-1].split('.')[-1].lower()
                    add(url, owner, field in {'src','imageurl','asseturl','fileurl','downloadurl','thumbnailurl'})
    for (kind, key), record in sorted(bundle['entities'].items()):
        for field, value in record.items():
            scan(value, [kind, key, field])
    for node in attachments:
        url = node['url']
        try:
            parsed = urlsplit(url)
            reference = parsed.scheme == 'https' and parsed.hostname == 'github.com' and bool(re.fullmatch(r'/[^/]+/[^/]+/(pull|issues)/\d+', parsed.path))
        except ValueError:
            reference = False
        add(url, ['attachment', node['id'], 'url'], not reference)
        scan(node.get('metadata', {}), ['attachment', node['id'], 'metadata'])
    if len(candidates) > 10000 or len(references) > 100000:
        raise SourceError('ASSET_COUNT_LIMIT')
    return [candidates[k] for k in sorted(candidates)], references


def download(fetcher, entry, directory, max_bytes, remaining):
    url = approved_url(entry['url'])
    temporary = directory / ('.part-' + entry['key'])
    if temporary.exists() or temporary.is_symlink():
        raise SourceError('ASSET_PARTIAL_REQUIRES_CLEANUP')
    deadline, size, checksum = time.monotonic() + 30, 0, hashlib.sha256()
    try:
        with fetcher.open(url) as response:
            length = response.headers.get('Content-Length')
            try:
                expected = int(length) if length is not None else None
                if expected is not None and expected < 0:raise ValueError()
            except (ValueError, TypeError):
                raise SourceError('ASSET_LENGTH_INVALID') from None
            if expected is not None and expected > max_bytes:
                raise SourceError('ASSET_TOO_LARGE')
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                raise SourceError('ASSET_ENCODING_DENIED')
            fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                while True:
                    if time.monotonic() >= deadline:raise SourceError('ASSET_TIMEOUT')
                    chunk = response.read1(min(65536, max_bytes + 1 - size))
                    if time.monotonic() >= deadline:raise SourceError('ASSET_TIMEOUT')
                    if not chunk:break
                    size += len(chunk)
                    if size > max_bytes:raise SourceError('ASSET_TOO_LARGE')
                    if size > remaining:raise SourceError('ASSET_TOTAL_BUDGET')
                    checksum.update(chunk);stream.write(chunk)
                stream.flush();os.fsync(stream.fileno())
            if expected is not None and size != expected:
                raise SourceError('ASSET_LENGTH_MISMATCH')
        sha = checksum.hexdigest();blob = directory / ('sha256-' + sha)
        if blob.exists() or blob.is_symlink():
            if blob_hash(blob, max_bytes) != (size, sha):raise SourceError('ASSET_CHECKSUM_MISMATCH')
        else:
            os.link(str(temporary), str(blob), follow_symlinks=False)
        return {'status': 'ARCHIVED', 'sha256': sha, 'size': size, 'file': blob.name,
                'reference': 'asset:sha256:' + sha}
    except SourceError:
        raise
    except (OSError, URLError, ValueError):
        raise SourceError('ASSET_TRANSFER_FAILED') from None
    finally:
        if temporary.exists() and not temporary.is_symlink():temporary.unlink()


def export_assets(source, fetcher, issues, associations, destination, resume=False,
                  max_asset_bytes=64 * 1024 * 1024, max_total_bytes=512 * 1024 * 1024, max_pages=10000):
    if any(type(n) is not int or n <= 0 for n in [max_asset_bytes,max_total_bytes,max_pages]) or max_pages > 100000:
        raise SourceError('ASSET_LIMIT')
    bundle = read_bundle(issues, associations)
    scope = graphql(source, SCOPE_QUERY, {'team': bundle['team_id']})
    if identity(scope['team']['id']) != bundle['team_id'] or identity(scope['organization']['id']) != bundle['organization_id']:
        raise SourceError('ASSET_SCOPE')
    directory = Path(destination).resolve();outside_git(directory)
    if not resume:directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    if not directory.is_dir() or directory.stat().st_mode & 0o077:raise SourceError('OUTPUT_PERMISSIONS')
    lock = os.open(str(directory / '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    writable, manifest = False, None
    try:
        try:fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:raise SourceError('EXPORT_LOCKED') from None
        if resume:
            manifest = json.loads(read_private(directory / 'manifest.json'))
            if not isinstance(manifest, dict) or manifest.get('schema_version') != 1 or manifest.get('status') not in {'RUNNING','FAILED','COMPLETE_FOR_DISCOVERED_ASSETS','COMPLETE_WITH_BLOCKED_ASSETS'}:
                raise SourceError('ASSET_MANIFEST_SHAPE')
            if manifest['source_fingerprint'] != bundle['fingerprint'] or manifest['profile'] != PROFILE or any(manifest.get(k) != bundle[k] for k in ['team_id','organization_id']):
                raise SourceError('ASSET_RESUME_SCOPE')
        else:
            manifest = {'schema_version':1,'source_fingerprint':bundle['fingerprint'],'profile':PROFILE,
                        'organization_id':bundle['organization_id'],'team_id':bundle['team_id'],
                        'started_at':datetime.now(timezone.utc).isoformat(),'pages':[],'assets':[],
                        'references':[],'status':'RUNNING','full_migration_backup':False}
        issue_ids = sorted(key for kind,key in bundle['entities'] if kind=='issue')
        index, cursor, seen, cursors, nodes, metadata_bytes = 0, None, set(), set(), [], 0
        def consume(data):
            nonlocal index, cursor
            rows, more, next_cursor = attachment_page(data,issue_ids[index],bundle['team_id'])
            for row in rows:
                key = identity(row['id'])
                if key in seen:raise SourceError('ASSET_DUPLICATE')
                seen.add(key)
            nodes.extend(rows)
            if more:
                if not next_cursor or (index,next_cursor) in cursors or next_cursor == cursor:raise SourceError('ASSET_CURSOR_LOOP')
                cursors.add((index,next_cursor));cursor = next_cursor
            else:index += 1;cursor = None
        if not isinstance(manifest['pages'],list) or len(manifest['pages']) > max_pages:raise SourceError('ASSET_LIMIT')
        for number, page in enumerate(manifest['pages'],1):
            if index >= len(issue_ids) or page['file'] != 'page-%06d.json' % number or page['issue'] != issue_ids[index] or page['cursor'] != cursor:
                raise SourceError('ASSET_PAGE_PROVENANCE')
            raw = read_private(directory / page['file']);metadata_bytes += len(raw)
            if metadata_bytes > max_total_bytes:raise SourceError('ASSET_TOTAL_BUDGET')
            if hashlib.sha256(raw).hexdigest() != page['sha256']:raise SourceError('CHECKSUM_MISMATCH')
            consume(json.loads(raw)['data'])
        if not isinstance(manifest['assets'], list) or len(manifest['assets']) > 10000 or not isinstance(manifest['references'],list):
            raise SourceError('ASSET_MANIFEST_SHAPE')
        keys = set()
        for entry in manifest['assets']:
            if not isinstance(entry,dict) or entry.get('status') not in {'PENDING','BLOCKED','ARCHIVED'} or not isinstance(entry.get('url'),str) or entry.get('key') != hashlib.sha256(entry['url'].encode()).hexdigest() or entry['key'] in keys:
                raise SourceError('ASSET_MANIFEST_SHAPE')
            keys.add(entry['key'])
            if entry['status']=='ARCHIVED':
                sha=entry['sha256']
                if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or entry['file'] != 'sha256-'+sha or type(entry['size']) is not int or entry['size'] < 0 or entry.get('reference') != 'asset:sha256:'+sha:raise SourceError('ASSET_MANIFEST_SHAPE')
                if blob_hash(directory / entry['file'],max_asset_bytes) != (entry['size'],sha):raise SourceError('ASSET_CHECKSUM_MISMATCH')
        known={p['file'] for p in manifest['pages']}
        if any(p.name not in known for p in directory.glob('page-*.json')):raise SourceError('ORPHAN_PAGE')
        if metadata_bytes + sum(e['size'] for e in manifest['assets'] if e['status']=='ARCHIVED') > max_total_bytes:
            raise SourceError('ASSET_TOTAL_BUDGET')
        if index < len(issue_ids) and (manifest['assets'] or manifest['references']):
            raise SourceError('ASSET_MANIFEST_SHAPE')
        if index == len(issue_ids) and (manifest['assets'] or manifest['references'] or manifest['status'].startswith('COMPLETE')):
            expected, expected_references = discover(bundle,nodes)
            if {(e['key'],e['url'],json.dumps(e['owners'])) for e in expected} != {(e['key'],e['url'],json.dumps(e['owners'])) for e in manifest['assets']} or manifest['references'] != expected_references:
                raise SourceError('ASSET_MANIFEST_SHAPE')
        writable=True;manifest['status']='RUNNING';manifest.pop('failure_code',None);checkpoint(directory,manifest)
        while index < len(issue_ids):
            if len(manifest['pages']) >= max_pages:raise SourceError('ASSET_PAGE_LIMIT')
            issue, previous = issue_ids[index], cursor
            data=graphql(source,ATTACHMENTS,{'id':issue,'after':cursor})
            raw=json.dumps({'data':data},ensure_ascii=False,sort_keys=True).encode()
            if len(raw)>16*1024*1024 or metadata_bytes+len(raw)>max_total_bytes:raise SourceError('ASSET_TOTAL_BUDGET')
            consume(data)  # validate scope before writing any provider payload
            filename='page-%06d.json' % (len(manifest['pages'])+1)
            private_file(directory / filename,raw);metadata_bytes+=len(raw)
            manifest['pages'].append({'file':filename,'issue':issue,'cursor':previous,'sha256':hashlib.sha256(raw).hexdigest()})
            checkpoint(directory,manifest)
        planned,references=discover(bundle,nodes)
        saved={entry['key']:entry for entry in manifest['assets']}
        if len(saved)!=len(manifest['assets']) or any(key not in {e['key'] for e in planned} for key in saved):raise SourceError('ASSET_MANIFEST_SHAPE')
        for entry in planned:
            old=saved.get(entry['key'])
            if old:
                if any(old.get(k)!=entry[k] for k in ['url','owners']):raise SourceError('ASSET_MANIFEST_SHAPE')
                if old['status']=='ARCHIVED':entry.update(old)
        manifest.update(assets=planned,references=references);checkpoint(directory,manifest)
        total=metadata_bytes+sum(e['size'] for e in planned if e['status']=='ARCHIVED')
        if total>max_total_bytes:raise SourceError('ASSET_TOTAL_BUDGET')
        for entry in planned:
            if entry['status']=='ARCHIVED':continue
            try:approved_url(entry['url'])
            except SourceError:
                entry.update(status='BLOCKED',code='ASSET_URL_DENIED');checkpoint(directory,manifest);continue
            if shutil.disk_usage(directory).free < min(max_asset_bytes,max_total_bytes-total)+1024*1024*1024:
                raise SourceError('DISK_RESERVE')
            entry.update(download(fetcher,entry,directory,max_asset_bytes,max_total_bytes-total));total+=entry['size']
            checkpoint(directory,manifest)
        manifest.update(status='COMPLETE_WITH_BLOCKED_ASSETS' if any(e['status']!='ARCHIVED' for e in planned) else 'COMPLETE_FOR_DISCOVERED_ASSETS',
                        finished_at=datetime.now(timezone.utc).isoformat())
        checkpoint(directory,manifest);return manifest
    except (SourceError,OSError,ValueError,KeyError,TypeError,AttributeError,KeyboardInterrupt) as error:
        code=str(error) if isinstance(error,SourceError) else ('INTERRUPTED' if isinstance(error,KeyboardInterrupt) else 'ASSET_INPUT_OR_IO')
        if writable:
            manifest.update(status='FAILED',failure_code=code);checkpoint(directory,manifest)
        raise SourceError(code) from None
    finally:os.close(lock)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['issues','associations','output']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--max-asset-bytes',type=int,default=64*1024*1024)
    parser.add_argument('--max-total-bytes',type=int,default=512*1024*1024)
    args=parser.parse_args()
    try:
        token=os.environ.get('LINEAR_API_KEY')
        result=export_assets(LinearHTTP(token),AssetHTTP(token),args.issues,args.associations,args.output,args.resume,args.max_asset_bytes,args.max_total_bytes)
        print(json.dumps({'status':result['status'],'attachment_pages':len(result['pages']),
                          'assets':len(result['assets']),'archived':sum(e['status']=='ARCHIVED' for e in result['assets'])}))
        return 0 if result['status']=='COMPLETE_FOR_DISCOVERED_ASSETS' else 3
    except (SourceError,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
        code=str(error) if isinstance(error,SourceError) else 'ASSET_INPUT_OR_IO'
        print(json.dumps({'code':code}),file=sys.stderr);return 130 if code=='INTERRUPTED' else 2


if __name__=='__main__':sys.exit(main())
