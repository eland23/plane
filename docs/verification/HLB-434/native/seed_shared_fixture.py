"""Documented synthetic setup inside the isolated .130 CLI container only."""
import os,sys,socket,json
from urllib.parse import urlparse,unquote
if not __debug__:
    print('OPTIMIZED_EXECUTION_DENIED',file=sys.stderr)
    raise SystemExit(2)
NS = 'plane-rehearsal-m-434-20261019'
try:
    u = urlparse(os.environ.get('DATABASE_URL',''))
    port = u.port
except ValueError:
    print('FIXTURE_DATABASE_DENIED',file=sys.stderr)
    raise SystemExit(2)
if not (u.scheme=='postgresql' and u.hostname==NS+'-db' and port==5432
        and u.path=='/plane_fixture_m' and u.username=='plane_fixture' and u.password
        and not u.query and not u.fragment and not os.environ.get('DATABASE_READ_REPLICA_URL')
        and os.environ.get('DJANGO_SETTINGS_MODULE')=='plane.settings.production'
        and os.environ.get('REDIS_URL')=='redis://'+NS+'-redis:6379/0'
        and os.environ.get('AMQP_URL')=='redis://'+NS+'-redis:6379/1'):
    print('FIXTURE_DATABASE_DENIED',file=sys.stderr)
    raise SystemExit(2)
if socket.gethostname()!=NS+'-cli':
    print('FIXTURE_CONTAINER_DENIED',file=sys.stderr)
    raise SystemExit(2)
if not (os.environ.get('AWS_S3_ENDPOINT_URL')=='http://'+NS+'-minio:9000'
        and os.environ.get('AWS_S3_BUCKET_NAME')=='plane-rehearsal-hlb434-m-20261019'
        and len(os.environ.get('AWS_ACCESS_KEY_ID',''))>=12 and len(os.environ.get('AWS_SECRET_ACCESS_KEY',''))>=24
        and os.environ.get('USE_MINIO')=='0' and os.environ.get('AWS_REGION')=='us-east-1'):
    print('FIXTURE_ASSET_DESTINATION_DENIED',file=sys.stderr)
    raise SystemExit(2)
import django
django.setup()
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from plane.db.models import User,Workspace,WorkspaceMember,Project,ProjectMember,Issue,IssueLink
from plane.db.models.session import SessionStore

config = settings.DATABASES.get('default',{})
if not (set(settings.DATABASES)=={'default'} and config.get('ENGINE')=='django.db.backends.postgresql'
        and config.get('HOST')==NS+'-db' and str(config.get('PORT'))=='5432'
        and config.get('NAME')=='plane_fixture_m' and config.get('USER')=='plane_fixture'
        and config.get('PASSWORD')==unquote(u.password)):
    raise RuntimeError('RESOLVED_FIXTURE_DATABASE_DENIED')

if not (settings.AWS_S3_ENDPOINT_URL=='http://'+NS+'-minio:9000'
        and settings.AWS_STORAGE_BUCKET_NAME=='plane-rehearsal-hlb434-m-20261019' and not settings.USE_MINIO):
    raise RuntimeError('RESOLVED_ASSET_DESTINATION_DENIED')
sys.path.insert(0,'/fixtures')
from pathlib import Path
from datetime import datetime
from plane.db.models import State,Module,ModuleIssue,Cycle,CycleIssue,IssueRelation,IssueComment,Page,ProjectPage,PageLog,FileAsset,IssueSequence
from asset_fixture import FIXTURES
G=json.loads(Path('/fixtures/shared_fixture_m.json').read_text())

with transaction.atomic():
    if Workspace.objects.filter(slug__in=[G['workspace']['slug'],G['other_workspace']['slug']]).exists() or User.objects.filter(id__in=G['members'].values()).exists():
        raise RuntimeError('FIXTURE_COLLISION')
    users={name:User.objects.create(id=identifier,email=name+'@shared-m.plane-rehearsal.invalid',username='shared-m-'+name,
        password=make_password(None),is_active=name!='inactive') for name,identifier in G['members'].items()}
    owner=users['owner']
    workspace=Workspace.objects.create(id=G['workspace']['id'],name='Shared fixture M',slug=G['workspace']['slug'],owner=owner)
    other=Workspace.objects.create(id=G['other_workspace']['id'],name='Other fixture M',slug=G['other_workspace']['slug'],owner=users['outsider'])
    WorkspaceMember.objects.create(workspace=other,member=users['outsider'],role=20)
    project=Project.objects.create(id=G['project']['id'],workspace=workspace,name='Shared fixture M',identifier='FAS',timezone='America/New_York')
    for name,role in [('owner',20),('member',15),('viewer',5)]:
        WorkspaceMember.objects.create(workspace=workspace,member=users[name],role=role)
        ProjectMember.objects.create(project=project,member=users[name],role=role)
    states={name:State.objects.create(id=value['id'],project=project,name=name,group=value['group'],color='#336699') for name,value in G['states'].items()}
    modules={name:Module.objects.create(id=identifier,project=project,name=name,lead=owner) for name,identifier in G['modules'].items()}
    issues={}
    for row in G['issues']:
        issue=Issue.objects.create(id=row['id'],project=project,name=row['name'],state=states[row['state']],
            parent_id=row['parent'],target_date=row['target_date'],created_by=owner)
        # Import setup preserves external sequence gaps without creating dummy issues.
        Issue.objects.filter(id=issue.id).update(sequence_id=row['sequence'],sort_order=row['sort_order'])
        IssueSequence.objects.filter(issue=issue).update(sequence=row['sequence'])
        issues[row['id']]=issue
        if row['module']:ModuleIssue.objects.create(project=project,module=modules[row['module']],issue=issue)
    for row in G['relations']:IssueRelation.objects.create(project=project,issue_id=row['issue'],related_issue_id=row['related_issue'],relation_type=row['type'])
    cycle=Cycle.objects.create(id=G['cycle']['id'],project=project,name=G['cycle']['name'],owned_by=owner,
        start_date=datetime.fromisoformat(G['cycle']['start'].replace('Z','+00:00')),end_date=datetime.fromisoformat(G['cycle']['end'].replace('Z','+00:00')),timezone=G['cycle']['timezone'])
    for issue in issues.values():CycleIssue.objects.create(project=project,cycle=cycle,issue=issue)
    for row in G['comments']:IssueComment.objects.create(id=row['id'],project=project,issue_id=G['issues'][2]['id'],actor_id=row['actor'],parent_id=row['parent'],comment_html=row['html'])
    inline_path='/api/assets/v2/workspaces/'+workspace.slug+'/projects/'+str(project.id)+'/'+G['assets']['inline']+'/'
    wiki=Page.objects.create(id=G['wiki']['id'],workspace=workspace,name=G['wiki']['name'],owned_by=owner,is_global=True,
        description_html=G['wiki']['html']+'<img src="'+inline_path+'">',created_by=owner)
    document=Page.objects.create(id=G['document']['id'],workspace=workspace,name=G['document']['name'],owned_by=owner,is_global=False,
        description_html=G['document']['html'],created_by=owner)
    ProjectPage.objects.create(project=project,workspace=workspace,page=document)
    PageLog.objects.create(workspace=workspace,page=document,entity_identifier=G['issues'][2]['id'],entity_name='issue',entity_type='issue')
    IssueLink.objects.create(id=G['document']['link_id'],project=project,issue_id=G['issues'][2]['id'],title=G['document']['name'],
        url='https://fixture-m.invalid/api/workspaces/'+workspace.slug+'/projects/'+str(project.id)+'/pages/'+str(document.id)+'/',created_by=owner)
    for name,row in zip(['inline','binary'],FIXTURES):
        FileAsset.objects.create(id=G['assets'][name],workspace=workspace,project=project,user=owner,asset=row['key'],
            page=wiki if name=='inline' else None,issue_id=G['issues'][2]['id'] if name=='binary' else None,
            entity_type='PAGE_DESCRIPTION' if name=='inline' else 'ISSUE_ATTACHMENT',is_uploaded=True,
            attributes={'name':name+'.'+('png' if name=='inline' else 'bin'),'type':row['headers']['ContentType']},size=len(row['body']))
    sessions={}
    for name in ['owner','member','viewer','outsider']:
        user=users[name];session=SessionStore()
        session['_auth_user_id']=str(user.pk);session['_auth_user_backend']=settings.AUTHENTICATION_BACKENDS[0]
        session['_auth_user_hash']=user.get_session_auth_hash();session.set_expiry(3600);session.save()
        sessions[name]=session.session_key
    print(json.dumps({'cookie_name':settings.SESSION_COOKIE_NAME,'sessions':sessions}))
