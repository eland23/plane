"""Run inside the existing Plane API container: SELECT-only consistent snapshot."""
import hashlib
import json
import os
import re

# Never export credential/user/content columns. Other table contents are hashed remotely.
WANTED = {
    'workspaces': ['id','slug','deleted_at'],
    'projects': ['id','workspace_id','identifier','name','external_source','external_id','deleted_at'],
    'issues': ['id','workspace_id','project_id','sequence_id','external_source','external_id','deleted_at'],
    'issue_sequences': ['id','project_id','issue_id','sequence','deleted'],
    'modules': ['id','workspace_id','project_id','name','external_source','external_id','deleted_at'],
    'cycles': ['id','workspace_id','project_id','name','external_source','external_id','deleted_at'],
    'labels': ['id','workspace_id','project_id','name','external_source','external_id','deleted_at'],
    'states': ['id','workspace_id','project_id','name','external_source','external_id','deleted_at'],
    'pages': ['id','workspace_id','external_source','external_id','deleted_at'],
    'initiatives': ['id','workspace_id','external_source','external_id','deleted_at'],
    'module_milestones': ['id','workspace_id','project_id','name','external_source','external_id','deleted_at'],
    'issue_links': ['id','workspace_id','project_id','issue_id','url','external_source','external_id','deleted_at'],
    'issue_attachments': ['id','workspace_id','project_id','issue_id','external_source','external_id','deleted_at'],
    'workspace_members': ['id','workspace_id','member_id','role','is_active','deleted_at'],
    'project_identifiers': ['id','workspace_id','project_id','name','deleted_at'],
}


def collect():
    try:
        import psycopg as driver
    except ImportError:
        import psycopg2 as driver
    connection=driver.connect(os.environ['DATABASE_URL'])
    try:
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            cursor.execute("SET LOCAL statement_timeout = '30000'")
            cursor.execute("SET LOCAL timezone = 'UTC'")
            cursor.execute("SELECT current_setting('transaction_read_only')")
            assert cursor.fetchone()[0]=='on'
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name")
            names=[r[0] for r in cursor.fetchall()]
            tables,rows={},{}
            for table in names:
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',table):raise ValueError()
                cursor.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",[table])
                columns=dict(cursor.fetchall());checksum=hashlib.sha256();count=0
                cursor.execute('SELECT row_to_json(t)::text FROM "'+table+'" t ORDER BY row_to_json(t)::text')
                while True:
                    batch=cursor.fetchmany(1000)
                    if not batch:break
                    for record, in batch:
                        checksum.update(record.encode());checksum.update(b'\n');count+=1
                    if count>1000000:raise ValueError()
                cursor.execute("SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=%s ORDER BY indexname",[table])
                indexes=hashlib.sha256(json.dumps(cursor.fetchall()).encode()).hexdigest()
                cursor.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=('public.' || %s)::regclass ORDER BY conname",[table])
                constraints=hashlib.sha256(json.dumps(cursor.fetchall()).encode()).hexdigest()
                tables[table]={'columns':columns,'count':count,'sha256':checksum.hexdigest(),'indexes_sha256':indexes,'constraints_sha256':constraints}
                if table in WANTED:
                    fields=[field for field in WANTED[table] if field in columns]
                    if not fields:continue
                    cursor.execute('SELECT '+','.join('"'+f+'"' for f in fields)+' FROM "'+table+'" ORDER BY '+','.join('"'+f+'"' for f in fields)+' LIMIT 100001')
                    selected=cursor.fetchall()
                    if len(selected)>100000:raise ValueError()
                    rows[table]=[dict(zip(fields,row)) for row in selected]
        return {'schema_version':1,'read_only':True,'isolation':'repeatable read',
                'tables':tables,'rows':rows,'credential_values_exported':False}
    finally:
        connection.rollback();connection.close()


if __name__=='__main__':
    try:
        value=json.dumps(collect(),sort_keys=True,default=str)
        if len(value.encode())>16*1024*1024:raise ValueError()
        print(value)
    except Exception:
        print(json.dumps({'code':'DESTINATION_SNAPSHOT_FAILED'}));raise SystemExit(2)
