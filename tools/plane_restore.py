#!/usr/bin/env python3
"""Readonly integrity commands for private Plane restore inputs and readbacks.

Asset format: manifest.json plus objects/<SHA256-of-key>.bin; files are streamed,
never extracted. Reports contain counts/hashes/error codes, never original keys.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tarfile

MAX_SNAPSHOT = 64 * 1024**2
MAX_ARCHIVE = 2 * 1024**3
MAX_MANIFEST = 4 * 1024**2
MAX_OBJECT = 512 * 1024**2
MAX_OBJECTS = 10000
HEX = re.compile(r'[0-9a-f]{64}\Z')
HEADERS = {'ContentType','CacheControl','ContentDisposition','ContentEncoding','ContentLanguage','Metadata'}


class IntegrityError(Exception):
    pass


def require(condition, code):
    if not condition:
        raise IntegrityError(code)


def stream_hash(stream, limit):
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        require(size <= limit, 'INPUT_TOO_LARGE')
        digest.update(chunk)
    return digest.hexdigest(), size


@contextmanager
def regular_input(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode), 'REGULAR_INPUT_REQUIRED')
        require(info.st_size <= limit, 'INPUT_TOO_LARGE')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            yield stream
        after = os.fstat(fd)
        require((info.st_size,info.st_mtime_ns,info.st_ctime_ns)==
                (after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'INPUT_CHANGED')
    finally:
        os.close(fd)


def unique_object(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def json_value(data,error_code):
    try:
        return json.loads(data,object_pairs_hook=unique_object,
                          parse_constant=lambda value:(_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeDecodeError,RecursionError):
        raise IntegrityError(error_code) from None


def validate_manifest(manifest):
    require(isinstance(manifest,dict) and set(manifest)=={'bucket','objects'}, 'MANIFEST_INVALID')
    require(isinstance(manifest['bucket'],str) and bool(manifest['bucket']), 'MANIFEST_INVALID')
    rows = manifest['objects']
    require(isinstance(rows,list) and len(rows)<=MAX_OBJECTS, 'MANIFEST_INVALID')
    seen = set()
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'archive_path','key','size','sha256','etag','last_modified','headers'}, 'MANIFEST_INVALID')
        key = row['key']
        require(isinstance(key,str) and 0<len(key.encode('utf-8'))<=1024 and '\x00' not in key, 'ASSET_KEY_INVALID')
        require(key not in seen, 'ASSET_KEY_DUPLICATE')
        seen.add(key)
        key_digest = hashlib.sha256(key.encode()).hexdigest()
        require(row['archive_path']=='objects/'+key_digest+'.bin', 'ASSET_ARCHIVE_PATH_INVALID')
        require(type(row['size']) is int and 0<=row['size']<=MAX_OBJECT, 'ASSET_SIZE_INVALID')
        require(isinstance(row['sha256'],str) and HEX.fullmatch(row['sha256']), 'ASSET_DIGEST_INVALID')
        require(isinstance(row['etag'],str) and isinstance(row['last_modified'],str), 'MANIFEST_INVALID')
        headers = row['headers']
        require(isinstance(headers,dict) and set(headers)<=HEADERS, 'ASSET_METADATA_INVALID')
        for name,value in headers.items():
            if name=='Metadata':
                require(isinstance(value,dict) and all(isinstance(k,str) and isinstance(v,str)
                    and not any(c in k+v for c in '\r\n') for k,v in value.items()), 'ASSET_METADATA_INVALID')
            else:
                require(isinstance(value,str) and '\r' not in value and '\n' not in value, 'ASSET_METADATA_INVALID')
    return rows


@contextmanager
def verified_assets(path, expected_digest):
    require(isinstance(expected_digest,str) and HEX.fullmatch(expected_digest), 'ARCHIVE_DIGEST_REQUIRED')
    with regular_input(path,MAX_ARCHIVE) as stream:
        actual_digest,_ = stream_hash(stream,MAX_ARCHIVE)
        require(actual_digest==expected_digest, 'ARCHIVE_HASH_MISMATCH')
        stream.seek(0)
        with tarfile.open(fileobj=stream,mode='r:',ignore_zeros=True) as archive:
            members = {}
            for member in archive:
                require(member.name not in members, 'ARCHIVE_MEMBER_DUPLICATE')
                require(member.isfile(), 'ARCHIVE_MEMBER_INVALID')
                require(len(members)<MAX_OBJECTS+1, 'ARCHIVE_TOO_MANY_MEMBERS')
                members[member.name] = member
            require('manifest.json' in members, 'MANIFEST_MISSING')
            require(members['manifest.json'].size<=MAX_MANIFEST, 'MANIFEST_TOO_LARGE')
            with archive.extractfile(members['manifest.json']) as data:
                manifest = json_value(data.read(),'MANIFEST_INVALID')
            rows = validate_manifest(manifest)
            expected_names = {'manifest.json'} | {row['archive_path'] for row in rows}
            require(expected_names<=set(members), 'ASSET_OBJECT_MISSING')
            require(set(members)==expected_names, 'ARCHIVE_MEMBER_UNEXPECTED')
            for row in rows:
                member = members[row['archive_path']]
                require(member.size==row['size'], 'ASSET_SIZE_MISMATCH')
                with archive.extractfile(member) as data:
                    digest,size = stream_hash(data,MAX_OBJECT)
                require(size==row['size'], 'ASSET_SIZE_MISMATCH')
                require(digest==row['sha256'], 'ASSET_HASH_MISMATCH')
            yield archive,manifest


def read_snapshot(path,expected_digest=None):
    with regular_input(path,MAX_SNAPSHOT) as stream:
        if expected_digest is not None:
            require(HEX.fullmatch(expected_digest), 'SNAPSHOT_DIGEST_REQUIRED')
            digest,_=stream_hash(stream,MAX_SNAPSHOT)
            require(digest==expected_digest, 'SNAPSHOT_HASH_MISMATCH')
            stream.seek(0)
        tables={}
        for line in stream:
            if not line.strip():continue
            row=json_value(line,'SNAPSHOT_INVALID')
            require(isinstance(row,dict) and set(row)=={'table','rows'}, 'SNAPSHOT_INVALID')
            name,rows=row['table'],row['rows']
            require(isinstance(name,str) and bool(name), 'SNAPSHOT_INVALID')
            require(name not in tables, 'SNAPSHOT_TABLE_DUPLICATE')
            require(isinstance(rows,list) and all(isinstance(item,dict) for item in rows), 'SNAPSHOT_INVALID')
            if rows:
                require(all(set(item)==set(rows[0]) for item in rows), 'SNAPSHOT_SCHEMA_INVALID')
            tables[name]=rows
        return tables


def row_values(rows):
    return Counter(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False) for row in rows)


def compare_database(expected_path,actual_path,expected_digest,preserve):
    expected=read_snapshot(expected_path,expected_digest)
    actual=read_snapshot(actual_path)
    if not preserve:
        require(set(expected)==set(actual), 'SNAPSHOT_TABLE_SET_MISMATCH')
        require(all(row_values(rows)==row_values(actual[name]) for name,rows in expected.items()), 'SNAPSHOT_ROW_MISMATCH')
    else:
        require(set(expected)<=set(actual), 'ORIGINAL_TABLE_LOST')
        for name,rows in expected.items():
            if not rows:continue
            fields=set(rows[0])
            require(all(fields<=set(row) for row in actual[name]), 'ORIGINAL_COLUMNS_LOST')
            projected=[{field:row[field] for field in fields} for row in actual[name]]
            require(not (row_values(rows)-row_values(projected)), 'ORIGINAL_ROW_CHANGED')
    return {'status':'PASS','tables':len(expected),'original_rows':sum(map(len,expected.values())),
            'mode':'preserve' if preserve else 'exact','original_values_preserved':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    audit = commands.add_parser('audit-assets')
    audit.add_argument('--archive',type=Path,required=True)
    audit.add_argument('--expected-sha256',required=True)
    compare = commands.add_parser('compare-asset')
    compare.add_argument('--archive',type=Path,required=True)
    compare.add_argument('--expected-sha256',required=True)
    compare.add_argument('--key-sha256',required=True)
    compare.add_argument('--readback',type=Path,required=True)
    database = commands.add_parser('compare-database')
    database.add_argument('--expected',type=Path,required=True)
    database.add_argument('--actual',type=Path,required=True)
    database.add_argument('--expected-sha256',required=True)
    database.add_argument('--allow-additions',action='store_true')
    args = parser.parse_args()
    try:
        if args.command=='compare-database':
            result=compare_database(args.expected,args.actual,args.expected_sha256,args.allow_additions)
        else:
            with verified_assets(args.archive,args.expected_sha256) as (_,manifest):
                if args.command=='compare-asset':
                    require(HEX.fullmatch(args.key_sha256), 'KEY_DIGEST_REQUIRED')
                    matches=[row for row in manifest['objects']
                             if hashlib.sha256(row['key'].encode()).hexdigest()==args.key_sha256]
                    require(len(matches)==1, 'ASSET_NOT_FOUND')
                    row=matches[0]
                    with regular_input(args.readback,MAX_OBJECT) as data:
                        digest,size=stream_hash(data,MAX_OBJECT)
                    require(size==row['size'], 'ASSET_SIZE_MISMATCH')
                    require(digest==row['sha256'], 'ASSET_HASH_MISMATCH')
                    result={'status':'PASS','key_sha256':args.key_sha256,'sha256':digest,'bytes':size}
                else:
                    result = {'status':'PASS','objects':len(manifest['objects']),
                              'bytes':sum(row['size'] for row in manifest['objects']),
                              'archive_sha256':args.expected_sha256}
        print(json.dumps(result))
        return 0
    except IntegrityError as error:
        print(json.dumps({'status':'FAIL','error':str(error)}))
    except (OSError,tarfile.TarError,OverflowError,UnicodeError,RecursionError):
        print(json.dumps({'status':'FAIL','error':'INPUT_UNAVAILABLE_OR_INVALID'}))
    return 1


if __name__=='__main__':
    raise SystemExit(main())
