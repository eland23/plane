"""Signed S3 operations for the run-owned .130 store; no original endpoint."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import sys

NS = 'plane-rehearsal-m-434-20261019'
BUCKET = 'plane-rehearsal-hlb434-m-20261019'
ENDPOINT = 'http://' + NS + '-minio:9000'


def connection(path):
    try:
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode&0o777!=0o600 or info.st_size>16384:
            raise ValueError()
        value=json.loads(path.read_text())
        if not (isinstance(value,dict) and set(value)=={'endpoint','bucket','access_key','secret_key'}
                and value['endpoint']==ENDPOINT and value['bucket']==BUCKET
                and isinstance(value['access_key'],str) and len(value['access_key'])>=12
                and isinstance(value['secret_key'],str) and len(value['secret_key'])>=24
                and socket.gethostname()==NS+'-sdk'):
            raise ValueError()
        return value
    except (OSError,ValueError,TypeError):
        print('SDK_FIXTURE_DENIED',file=sys.stderr)
        raise SystemExit(2)


def main():
    if not __debug__:
        print('OPTIMIZED_EXECUTION_DENIED',file=sys.stderr)
        return 2
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['ready','restore','snapshot','corrupt','restore-fixture'])
    parser.add_argument('--connection',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--readback',type=Path,default=Path('/readback'))
    args=parser.parse_args()
    config=connection(args.connection)
    sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'tools'))
    from plane_restore import verified_assets, require, HEADERS
    from asset_fixture import FIXTURES
    os.environ['AWS_EC2_METADATA_DISABLED']='true'
    with verified_assets(args.archive,args.expected_sha256) as (archive,manifest):
        rows=manifest['objects']
        require(sum(row['size'] for row in rows)<=16*1024**2,'COMPONENT_ASSET_CAPACITY')
        require(not ({row['key'] for row in rows}&{row['key'] for row in FIXTURES}),'FIXTURE_COLLISION')
        for row in FIXTURES:
            require(hashlib.sha256(row['body']).hexdigest()==row['sha256'],'GOLDEN_FIXTURE_CHANGED')
        import boto3
        from botocore import UNSIGNED
        from botocore.config import Config
        from botocore.exceptions import ClientError
        options=dict(endpoint_url=config['endpoint'],region_name='us-east-1')
        limits=dict(connect_timeout=5,read_timeout=10,retries={'max_attempts':1},s3={'addressing_style':'path'})
        client=boto3.client('s3',**options,aws_access_key_id=config['access_key'],
                            aws_secret_access_key=config['secret_key'],config=Config(**limits))
        bucket=config['bucket']
        if args.action=='ready':
            client.list_buckets()
        elif args.action=='restore':
            require(not client.list_buckets().get('Buckets'),'DESTINATION_NOT_EMPTY')
            client.create_bucket(Bucket=bucket)
            for row in rows:
                with archive.extractfile(row['archive_path']) as stream:data=stream.read()
                client.put_object(Bucket=bucket,Key=row['key'],Body=data,**row['headers'])
            for row in FIXTURES:
                client.put_object(Bucket=bucket,Key=row['key'],Body=row['body'],**row['headers'])
        elif args.action in ['corrupt','restore-fixture']:
            row=FIXTURES[1]
            head=client.head_object(Bucket=bucket,Key=row['key'])
            require(head['Metadata']==row['headers']['Metadata'],'FIXTURE_MARKER_REQUIRED')
            body=bytes([row['body'][0]^1])+row['body'][1:] if args.action=='corrupt' else row['body']
            client.put_object(Bucket=bucket,Key=row['key'],Body=body,**row['headers'])
        else:
            require(args.readback.is_dir() and not any(args.readback.iterdir()),'READBACK_DIRECTORY_REQUIRED')
            results=[]
            total_read=0
            for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket):
                for item in page.get('Contents',[]):
                    require(len(results)<10002,'READBACK_OBJECT_CAPACITY')
                    response=client.get_object(Bucket=bucket,Key=item['Key'])
                    key_digest=hashlib.sha256(item['Key'].encode()).hexdigest()
                    target=args.readback/(key_digest+'.bin')
                    with target.open('xb') as output:
                        target.chmod(0o600)
                        body=response['Body']
                        try:
                            for block in iter(lambda:body.read(1024*1024),b''):
                                total_read+=len(block)
                                require(total_read<=32*1024**2,'READBACK_BYTE_CAPACITY')
                                output.write(block)
                        finally:body.close()
                    results.append({'key_sha256':key_digest,'headers':{k:v for k,v in response.items() if k in HEADERS}})
            anonymous=boto3.client('s3',**options,config=Config(signature_version=UNSIGNED,**limits))
            try:
                response=anonymous.get_object(Bucket=bucket,Key=FIXTURES[1]['key'])
                status=response['ResponseMetadata']['HTTPStatusCode'];response['Body'].close()
            except ClientError as error:status=error.response['ResponseMetadata']['HTTPStatusCode']
            target=args.readback/'objects.json'
            with target.open('x') as output:
                target.chmod(0o600)
                json.dump({'objects':results,'anonymous_status':status},output)
        print(json.dumps({'action':args.action,'status':'PASS','sdk_version':boto3.__version__,'python':sys.version.split()[0]}))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'FAIL','error_type':type(error).__name__}),file=sys.stderr)
        raise SystemExit(1)
