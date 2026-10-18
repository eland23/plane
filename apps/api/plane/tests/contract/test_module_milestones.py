"""Public milestone commands exercise real persistence, scope and conflicts."""
from datetime import date

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from plane.db.models import User, Workspace, WorkspaceMember, Project, ProjectMember, Module, ModuleIssue, Issue
from plane.app.services.milestones import (
    create_milestone, update_milestone, list_milestones, assign_milestone,
    delete_milestone, MilestoneConflict,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def scope():
    member = User.objects.create(email='milestone@example.invalid', username='milestone')
    workspace = Workspace.objects.create(name='Milestone fixture', slug='milestone-fixture', owner=member)
    project = Project.objects.create(name='FAS', identifier='FAS', workspace=workspace)
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    ProjectMember.objects.create(project=project, member=member, role=15)
    module = Module.objects.create(project=project, name='Wardrobe')
    issue = Issue.objects.create(project=project, name='FAS-2 original')
    ModuleIssue.objects.create(project=project, module=module, issue=issue)
    return member, workspace, project, module, issue


def test_milestone_lifecycle_exact_values_clear_order_archive_and_delete(scope):
    user, _, _, module, _ = scope
    first = create_milestone(user, module.id, {'name':'First release','description':'Original scope',
        'target_date':'2026-11-03','sort_order':20})
    second = create_milestone(user, module.id, {'name':'Preview','sort_order':10})
    assert [row.name for row in list_milestones(user,module.id)] == ['Preview','First release']
    assert first.target_date == date(2026,11,3) and first.created_by_id==user.pk
    update_milestone(user,module.id,first.id,{'target_date':None,'status':'cancelled','sort_order':5,'archived':True})
    first.refresh_from_db()
    assert first.target_date is None and first.status == 'cancelled' and first.archived_at is not None
    assert first.description == 'Original scope' and first.updated_by_id==user.pk
    assert [row.id for row in list_milestones(user,module.id)] == [second.id]
    update_milestone(user,module.id,first.id,{'archived':False})
    assert [row.id for row in list_milestones(user,module.id)] == [first.id,second.id]
    delete_milestone(user,module.id,second.id)
    assert [row.id for row in list_milestones(user,module.id,include_archived=True)] == [first.id]


def test_milestone_assignment_replaces_one_value_and_delete_conflicts_until_clear(scope):
    from plane.db.models import IssueMilestone
    user, _, project, module, issue = scope
    first = create_milestone(user,module.id,{'name':'First'})
    second = create_milestone(user,module.id,{'name':'Second'})
    other = Issue.objects.create(project=project,name='FAS-5 unrelated')
    ModuleIssue.objects.create(project=project,module=module,issue=other)
    assign_milestone(user,module.id,issue.id,first.id)
    assign_milestone(user,module.id,other.id,first.id)
    assign_milestone(user,module.id,issue.id,second.id)
    assert IssueMilestone.objects.get(issue=issue).milestone_id == second.id
    assert IssueMilestone.objects.get(issue=other).milestone_id == first.id
    with pytest.raises(MilestoneConflict): delete_milestone(user,module.id,second.id)
    assert IssueMilestone.objects.get(issue=issue).milestone_id == second.id
    assign_milestone(user,module.id,issue.id,None)
    assert not IssueMilestone.objects.filter(issue=issue).exists()
    delete_milestone(user,module.id,second.id)
    assert IssueMilestone.objects.get(issue=other).milestone_id == first.id
    assert set(ModuleIssue.objects.filter(module=module).values_list('issue_id',flat=True)) == {issue.id,other.id}


@pytest.mark.parametrize('values',[{'name':' '},{'name':'x'*256},{'target_date':'2026-02-30'},
    {'status':'invented'},{'sort_order':float('nan')},{'sort_order':True},{'archived':'yes'},
    {'external_id':'forged'},{'workspace':'forged'},{'description':None}])
def test_milestone_validation_keeps_saved_record_usable(scope,values):
    user,_,_,module,_=scope
    row=create_milestone(user,module.id,{'name':'Original','target_date':'2026-12-01'})
    with pytest.raises(ValidationError):update_milestone(user,module.id,row.id,values)
    row.refresh_from_db()
    assert row.name=='Original' and row.target_date==date(2026,12,1)
    update_milestone(user,module.id,row.id,{'name':'Recovered'})
    row.refresh_from_db();assert row.name=='Recovered'


@pytest.mark.parametrize('denial',['viewer','inactive-workspace','inactive-project','outsider','inactive-user'])
def test_milestone_authorization_denies_reads_and_writes(scope,denial):
    user,workspace,project,module,issue=scope
    row=create_milestone(user,module.id,{'name':'Protected'})
    if denial=='viewer':ProjectMember.objects.filter(member=user,project=project).update(role=5)
    if denial=='inactive-workspace':WorkspaceMember.objects.filter(member=user,workspace=workspace).update(is_active=False)
    if denial=='inactive-project':ProjectMember.objects.filter(member=user,project=project).update(is_active=False)
    if denial=='outsider':user=User.objects.create(email='outsider@example.invalid',username='outsider')
    if denial=='inactive-user':user.is_active=False;user.save()
    if denial=='viewer':
        assert [item.name for item in list_milestones(user,module.id)]==['Protected']
    else:
        with pytest.raises(PermissionDenied):list_milestones(user,module.id)
    for command in [lambda:update_milestone(user,module.id,row.id,{'name':'Leaked'}),
                    lambda:delete_milestone(user,module.id,row.id),lambda:create_milestone(user,module.id,{'name':'Forged'}),
                    lambda:assign_milestone(user,module.id,issue.id,row.id)]:
        with pytest.raises(PermissionDenied):command()
    row.refresh_from_db();assert row.name=='Protected'


def test_milestone_rejects_foreign_module_issue_and_archived_target(scope):
    from plane.db.models import IssueMilestone
    user,_,project,module,issue=scope
    first=create_milestone(user,module.id,{'name':'Target'})
    foreign=Module.objects.create(project=project,name='Foreign module')
    second=create_milestone(user,foreign.id,{'name':'Foreign target'})
    for command in [lambda:assign_milestone(user,module.id,issue.id,second.id),
                    lambda:update_milestone(user,foreign.id,first.id,{'name':'Changed'})]:
        with pytest.raises(PermissionDenied):command()
    update_milestone(user,module.id,first.id,{'archived':True})
    with pytest.raises(ValidationError):assign_milestone(user,module.id,issue.id,first.id)
    assert not IssueMilestone.objects.filter(issue=issue).exists()
    update_milestone(user,module.id,first.id,{'archived':False})
    assign_milestone(user,module.id,issue.id,first.id)
    with pytest.raises(PermissionDenied):assign_milestone(user,foreign.id,issue.id,None)
    assert IssueMilestone.objects.get(issue=issue).milestone_id==first.id


def test_native_milestone_source_identity_is_paired_unique_and_retained(scope):
    from plane.db.models import ModuleMilestone
    _,_,project,module,_=scope
    row=ModuleMilestone.objects.create(project=project,module=module,name='Imported',
        external_source='linear:fixture',external_id='milestone-uuid')
    for values in [{'external_source':'linear:fixture'}, {'external_source':'','external_id':''},
                   {'external_source':'linear:fixture','external_id':'milestone-uuid'}]:
        with pytest.raises(IntegrityError),transaction.atomic():
            ModuleMilestone.objects.create(project=project,module=module,name='Invalid',**values)
    ModuleMilestone.objects.filter(pk=row.pk).update(deleted_at=row.created_at)
    with pytest.raises(IntegrityError),transaction.atomic():
        ModuleMilestone.objects.create(project=project,module=module,name='Replay',
            external_source='linear:fixture',external_id='milestone-uuid')


def test_milestone_direct_scope_and_identity_rebinding_are_rejected(scope):
    from plane.db.models import ModuleMilestone
    _,workspace,project,module,_=scope
    row=ModuleMilestone.objects.create(project=project,module=module,name='Imported',
        external_source='linear:fixture',external_id='original-milestone')
    foreign=Module.objects.create(project=project,name='Foreign')
    for values in [{'external_id':'replacement'},{'module_id':foreign.pk}]:
        with pytest.raises(IntegrityError),transaction.atomic():
            ModuleMilestone.objects.filter(pk=row.pk).update(**values)
    row.refresh_from_db();assert row.external_id=='original-milestone' and row.module_id==module.id
    other=Workspace.objects.create(name='Other',slug='other-milestone-fixture',owner=workspace.owner)
    other_project=Project.objects.create(name='Other',identifier='OTH',workspace=other)
    with pytest.raises(IntegrityError),transaction.atomic():
        ModuleMilestone.objects.create(project=other_project,module=module,name='Invalid scope')


@pytest.mark.django_db(transaction=True)
def test_milestone_schema_reverse_refuses_to_discard_native_data(scope):
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from plane.db.models import ModuleMilestone
    user,_,_,module,_=scope
    row=create_milestone(user,module.id,{'name':'Original native milestone'})
    with pytest.raises(RuntimeError,match='Cannot remove native milestone data'):
        MigrationExecutor(connection).migrate([('db','0123_issue_link_source_identity')])
    assert ModuleMilestone.objects.get(pk=row.pk).name=='Original native milestone'


@pytest.mark.django_db(transaction=True)
def test_milestone_assignment_and_delete_serialize_without_losing_membership(scope):
    import threading
    import time
    from django.db import connections
    from plane.db.models import IssueMilestone
    user,_,_,module,issue=scope
    row=create_milestone(user,module.id,{'name':'Concurrent target'})
    assigned,release=threading.Event(),threading.Event()
    results={}
    def writer():
        try:
            with transaction.atomic():
                assign_milestone(user,module.id,issue.id,row.id)
                assigned.set()
                if not release.wait(20):raise RuntimeError('Writer release timeout')
        except Exception as error:results['writer_error']=type(error).__name__
        finally:connections.close_all()
    def deleter():
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SET application_name='hlb465_delete_contract'")
                cursor.execute("SET statement_timeout='15s'")
            delete_milestone(user,module.id,row.id)
            results['delete']='deleted'
        except MilestoneConflict:results['delete']='conflict'
        except Exception as error:results['delete_error']=type(error).__name__
        finally:connections.close_all()
    first=threading.Thread(target=writer);second=threading.Thread(target=deleter)
    first.start()
    try:
        assert assigned.wait(10),'assignment did not reach lock boundary'
        second.start()
        waited=False
        for _ in range(100):
            with connections['default'].cursor() as cursor:
                cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name='hlb465_delete_contract' AND wait_event_type='Lock')")
                waited=cursor.fetchone()[0]
            if waited:break
            time.sleep(.05)
        assert waited,'competing delete did not wait on the scope lock'
    finally:
        release.set();first.join(25)
        if second.ident:second.join(25)
    assert not first.is_alive() and not second.is_alive()
    assert results=={'delete':'conflict'},results
    assert IssueMilestone.objects.get(issue=issue).milestone_id==row.id
    row.refresh_from_db();assert row.deleted_at is None
