"""Native link identity uses the real PostgreSQL schema and public serializers."""
import pytest
from django.db import IntegrityError, transaction
from plane.db.models import User, Workspace, Project, Issue, IssueLink
from plane.app.serializers import IssueLinkSerializer

pytestmark = pytest.mark.django_db


@pytest.fixture
def link_scope():
    user = User.objects.create(email='link-fixture@example.invalid', username='link-fixture')
    workspace = Workspace.objects.create(name='Migration fixture', slug='migration-link-fixture', owner=user)
    project = Project.objects.create(name='FAS fixture', identifier='FAS', workspace=workspace)
    issue = Issue.objects.create(name='Original FAS issue', project=project)
    return workspace, project, issue


def test_import_link_identity_is_scoped_unique_and_manual_links_are_preserved(link_scope):
    workspace, project, issue = link_scope
    manual = IssueLink.objects.create(project=project, issue=issue, url='https://example.invalid/manual')
    imported = IssueLink.objects.create(project=project, issue=issue, url='https://example.invalid/source',
        external_source='linear:fixture-org', external_id='source-attachment-1')
    with pytest.raises(IntegrityError), transaction.atomic():
        IssueLink.objects.create(project=project, issue=issue, url='https://example.invalid/duplicate',
            external_source='linear:fixture-org', external_id='source-attachment-1')
    manual.refresh_from_db();imported.refresh_from_db()
    assert manual.url=='https://example.invalid/manual' and manual.external_id is None
    assert imported.external_id=='source-attachment-1'
    IssueLink.objects.filter(pk=imported.pk).update(deleted_at=imported.created_at)
    with pytest.raises(IntegrityError), transaction.atomic():
        IssueLink.objects.create(project=project, issue=issue, url='https://example.invalid/replay',
            external_source='linear:fixture-org', external_id='source-attachment-1')


def test_ordinary_link_serializer_cannot_rebind_import_identity(link_scope):
    _, project, issue = link_scope
    imported=IssueLink.objects.create(project=project, issue=issue, title='Original', url='https://example.invalid/source',
        external_source='linear:fixture-org',external_id='source-attachment-1')
    serializer=IssueLinkSerializer(imported,data={'title':'Updated','external_id':'attacker-id','external_source':'other'},partial=True)
    assert serializer.is_valid(),serializer.errors
    serializer.save();imported.refresh_from_db()
    assert imported.title=='Updated' and imported.external_id=='source-attachment-1'
    assert imported.external_source=='linear:fixture-org'


def test_partial_or_empty_source_binding_is_rejected_by_database(link_scope):
    _, project, issue=link_scope
    for source,key in [('linear:fixture-org',None),(None,'source-attachment-1'),('','')]:
        with pytest.raises(IntegrityError), transaction.atomic():
            IssueLink.objects.create(project=project,issue=issue,url='https://example.invalid/invalid',external_source=source,external_id=key)


def test_bound_source_identity_cannot_be_rewritten_by_a_direct_update(link_scope):
    _, project, issue=link_scope
    imported=IssueLink.objects.create(project=project,issue=issue,url='https://example.invalid/source',
        external_source='linear:fixture-org',external_id='source-attachment-1')
    with pytest.raises(IntegrityError), transaction.atomic():
        IssueLink.objects.filter(pk=imported.pk).update(external_id='different-source')
    imported.refresh_from_db()
    assert imported.external_id=='source-attachment-1'


@pytest.mark.django_db(transaction=True)
def test_schema_roundtrip_preserves_manual_links_and_refuses_to_drop_bound_identity(link_scope):
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    _, project, issue=link_scope
    manual=IssueLink.objects.create(project=project,issue=issue,url='https://example.invalid/manual',title='Existing')
    before=('db','0122_alter_draftissue_assignees_alter_issue_assignees_and_more')
    after=('db','0123_issue_link_source_identity')
    executor=MigrationExecutor(connection)
    try:
        executor.migrate([before])
        old=executor.loader.project_state([before]).apps.get_model('db','IssueLink')
        assert old.objects.get(pk=manual.pk).url=='https://example.invalid/manual'
        executor=MigrationExecutor(connection);executor.migrate([after])
        manual.refresh_from_db()
        assert manual.title=='Existing' and manual.external_id is None
        imported=IssueLink.objects.create(project=project,issue=issue,url='https://example.invalid/source',
            external_source='linear:fixture-org',external_id='source-attachment-1')
        with pytest.raises(RuntimeError,match='Cannot remove imported link identities'):
            MigrationExecutor(connection).migrate([before])
        imported.refresh_from_db();manual.refresh_from_db()
        assert imported.external_id=='source-attachment-1'
        assert manual.url=='https://example.invalid/manual'
    finally:
        MigrationExecutor(connection).migrate([after])


def test_source_identity_can_exist_in_another_workspace_but_cannot_be_moved(link_scope):
    workspace, project, issue=link_scope
    other=Workspace.objects.create(name='Other workspace',slug='other-link-fixture',owner=workspace.owner)
    other_project=Project.objects.create(name='Other FAS',identifier='FAS',workspace=other)
    other_issue=Issue.objects.create(name='Other issue',project=other_project)
    for target_project,target_issue in [(project,issue),(other_project,other_issue)]:
        IssueLink.objects.create(project=target_project,issue=target_issue,url='https://example.invalid/scoped',
            external_source='linear:fixture-org',external_id='shared-source-uuid')
    movable=IssueLink.objects.create(project=project,issue=issue,url='https://example.invalid/move',
        external_source='linear:fixture-org',external_id='unique-source-uuid')
    with pytest.raises(IntegrityError), transaction.atomic():
        IssueLink.objects.filter(pk=movable.pk).update(workspace_id=other.id)
    movable.refresh_from_db()
    assert movable.workspace_id==workspace.id


@pytest.mark.django_db(transaction=True)
def test_concurrent_import_commits_before_reversal_check_and_identity_is_preserved(link_scope):
    import threading
    import time
    from django.db import connection, connections
    from django.db.migrations.executor import MigrationExecutor
    _, project, issue=link_scope
    inserted,commit=threading.Event(),threading.Event()
    results={}
    def writer():
        try:
            with transaction.atomic():
                row=IssueLink.objects.create(project_id=project.pk,issue_id=issue.pk,url='https://example.invalid/concurrent',
                    external_source='linear:fixture-org',external_id='concurrent-attachment')
                results['link']=row.pk;inserted.set()
                if not commit.wait(20):raise RuntimeError('Writer release timeout')
        except Exception as error:results['writer_error']=type(error).__name__
        finally:connections.close_all()
    def reverse():
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SET application_name = 'hlb464_reverse_contract'")
            MigrationExecutor(connections['default']).migrate([
                ('db','0122_alter_draftissue_assignees_alter_issue_assignees_and_more')])
            results['reverse']='applied'
        except RuntimeError as error:
            results['reverse']='blocked' if 'Cannot remove imported link identities' in str(error) else 'unexpected'
        except Exception as error:results['reverse_error']=type(error).__name__
        finally:connections.close_all()
    write_thread=threading.Thread(target=writer)
    reverse_thread=threading.Thread(target=reverse)
    write_thread.start()
    try:
        assert inserted.wait(10),'writer did not reach the intended boundary'
        reverse_thread.start()
        waiting=False;deadline=time.monotonic()+15
        while time.monotonic()<deadline and reverse_thread.is_alive():
            with connection.cursor() as cursor:
                cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name='hlb464_reverse_contract' AND wait_event_type='Lock')")
                waiting=cursor.fetchone()[0]
            if waiting:break
            time.sleep(0.02)
        assert waiting,'reversal did not reach the competing-write boundary'
        commit.set();write_thread.join(20);reverse_thread.join(20)
        assert not write_thread.is_alive() and not reverse_thread.is_alive()
        assert 'writer_error' not in results and 'reverse_error' not in results
        assert results['reverse']=='blocked'
        assert IssueLink.objects.get(pk=results['link']).external_id=='concurrent-attachment'
    finally:
        commit.set();write_thread.join(20)
        if reverse_thread.ident is not None:reverse_thread.join(20)
        MigrationExecutor(connection).migrate([('db','0123_issue_link_source_identity')])
