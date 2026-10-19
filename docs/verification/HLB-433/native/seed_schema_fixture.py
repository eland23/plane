"""Documented synthetic setup inside the isolated .130 CLI container only."""
import os,sys,socket,json
from urllib.parse import urlparse,unquote
if not __debug__:
    raise RuntimeError('OPTIMIZED_EXECUTION_DENIED')
NS = 'plane-rehearsal-api-433-20261018'
try:
    u = urlparse(os.environ.get('DATABASE_URL',''))
    port = u.port
except ValueError:
    print('FIXTURE_DATABASE_DENIED',file=sys.stderr)
    raise SystemExit(2)
if not (u.scheme=='postgresql' and u.hostname==NS+'-db' and port==5432
        and u.path=='/plane_schema_good' and u.username=='plane_fixture' and u.password
        and not u.query and not u.fragment and not os.environ.get('DATABASE_READ_REPLICA_URL')
        and os.environ.get('DJANGO_SETTINGS_MODULE')=='plane.settings.production'
        and os.environ.get('REDIS_URL')=='redis://'+NS+'-redis:6379/0'
        and os.environ.get('AMQP_URL')=='redis://'+NS+'-redis:6379/1'):
    print('FIXTURE_DATABASE_DENIED',file=sys.stderr)
    raise SystemExit(2)
if socket.gethostname()!=NS+'-cli':
    print('FIXTURE_CONTAINER_DENIED',file=sys.stderr)
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
        and config.get('NAME')=='plane_schema_good' and config.get('USER')=='plane_fixture'
        and config.get('PASSWORD')==unquote(u.password)):
    raise RuntimeError('RESOLVED_FIXTURE_DATABASE_DENIED')

with transaction.atomic():
    if User.objects.filter(id='43300000-0000-4000-8000-000000000001').exists() or Workspace.objects.filter(slug='plane-image-schema-433').exists():
        raise RuntimeError('FIXTURE_COLLISION')
    user=User.objects.create(id='43300000-0000-4000-8000-000000000001',email='image-schema@plane-rehearsal.invalid',username='image-schema-433',password=make_password(None))
    workspace=Workspace.objects.create(id='43300000-0000-4000-8000-000000000002',name='Image schema fixture',slug='plane-image-schema-433',owner=user)
    WorkspaceMember.objects.create(workspace=workspace,member=user,role=20)
    project=Project.objects.create(id='43300000-0000-4000-8000-000000000003',workspace=workspace,name='Image schema fixture',identifier='IMG')
    ProjectMember.objects.create(project=project,member=user,role=20)
    issue=Issue.objects.create(id='43300000-0000-4000-8000-000000000004',project=project,name='Existing supported issue fixture')
    IssueLink.objects.create(id='43300000-0000-4000-8000-000000000005',project=project,issue=issue,url='https://example.invalid/plane-schema-fixture',title='Existing supported schema fixture',created_by=user)
    session=SessionStore()
    session['_auth_user_id']=str(user.pk)
    session['_auth_user_backend']=settings.AUTHENTICATION_BACKENDS[0]
    session['_auth_user_hash']=user.get_session_auth_hash()
    session.set_expiry(3600)
    session.save()
    print(json.dumps({'cookie_name':settings.SESSION_COOKIE_NAME,'session_key':session.session_key}))
