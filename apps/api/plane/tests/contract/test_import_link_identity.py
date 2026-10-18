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
