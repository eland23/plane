"""Native milestone command boundary. UI/HTTP adapters must preserve this scope.

All commands lock the owning module first. Assignment then locks its issue, so
assignment, clearing and destructive operations cannot race within a module.
Source provenance is intentionally unavailable to ordinary editing commands.
"""
from datetime import date
import math

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from plane.db.models import (
    Module, ModuleIssue, ModuleMilestone, Issue, IssueMilestone,
    WorkspaceMember, ProjectMember,
)


class MilestoneConflict(Exception):
    """An assignment must be explicitly cleared before destructive deletion."""


def _scope(actor, module_id, write=True):
    if not actor or not actor.is_active:
        raise PermissionDenied('Milestone scope unavailable')
    minimum_role = 15 if write else 5
    module = Module.objects.select_for_update().filter(pk=module_id,project__deleted_at__isnull=True,
        workspace__deleted_at__isnull=True).first()
    if not module or not WorkspaceMember.objects.filter(workspace_id=module.workspace_id,member_id=actor.pk,
        is_active=True,role__gte=minimum_role).exists() or not ProjectMember.objects.filter(project_id=module.project_id,
        member_id=actor.pk,is_active=True,role__gte=minimum_role).exists():
        raise PermissionDenied('Milestone scope unavailable')
    return module


def _milestone(module, milestone_id):
    row = ModuleMilestone.objects.filter(pk=milestone_id,module_id=module.pk,
        project_id=module.project_id,workspace_id=module.workspace_id).first()
    if row is None:
        raise PermissionDenied('Milestone scope unavailable')
    return row


def _values(values, creating=False):
    allowed = {'name','description','target_date','status','sort_order','archived'}
    if not isinstance(values,dict) or set(values)-allowed:
        raise ValidationError('Unsupported milestone fields')
    result = dict(values)
    if creating and 'name' not in result:
        raise ValidationError({'name':'Required'})
    if 'name' in result:
        if not isinstance(result['name'],str) or not result['name'].strip() or len(result['name'])>255:
            raise ValidationError({'name':'Use a nonempty name of at most 255 characters'})
        result['name'] = result['name'].strip()
    if 'description' in result and (not isinstance(result['description'],str) or len(result['description'])>250000):
        raise ValidationError({'description':'Use text of at most 250000 characters'})
    if 'target_date' in result and result['target_date'] is not None:
        value = result['target_date']
        try:
            if isinstance(value,str):value=date.fromisoformat(value)
            if type(value) is not date:raise ValueError
        except (ValueError,TypeError):
            raise ValidationError({'target_date':'Use an ISO calendar date or null'}) from None
        result['target_date'] = value
    if 'status' in result and result['status'] not in ('planned','completed','cancelled'):
        raise ValidationError({'status':'Unsupported milestone status'})
    if 'sort_order' in result and (type(result['sort_order']) not in (int,float) or not math.isfinite(result['sort_order'])):
        raise ValidationError({'sort_order':'Use a finite number'})
    if 'archived' in result:
        if type(result['archived']) is not bool:raise ValidationError({'archived':'Use a boolean'})
        result['archived_at'] = timezone.now() if result.pop('archived') else None
    return result


@transaction.atomic
def create_milestone(actor, module_id, values):
    module = _scope(actor,module_id)
    return ModuleMilestone.objects.create(project_id=module.project_id,workspace_id=module.workspace_id,
        module=module,**_values(values,creating=True))


@transaction.atomic
def update_milestone(actor, module_id, milestone_id, values):
    module = _scope(actor,module_id)
    row = _milestone(module,milestone_id)
    for key,value in _values(values).items():setattr(row,key,value)
    row.save()
    return row


@transaction.atomic
def list_milestones(actor, module_id, include_archived=False):
    module = _scope(actor,module_id,write=False)
    rows = ModuleMilestone.objects.filter(module=module,project_id=module.project_id,workspace_id=module.workspace_id)
    if not include_archived:rows=rows.filter(archived_at__isnull=True)
    # Materialize before the transaction releases the authorization/scope lock.
    return list(rows.order_by('sort_order','id'))


@transaction.atomic
def assign_milestone(actor, module_id, issue_id, milestone_id):
    module = _scope(actor,module_id)
    issue = Issue.objects.select_for_update().filter(pk=issue_id,project_id=module.project_id,
        workspace_id=module.workspace_id).first()
    if not issue or not ModuleIssue.objects.filter(module=module,issue=issue,
        project_id=module.project_id,workspace_id=module.workspace_id).exists():
        raise PermissionDenied('Milestone scope unavailable')
    existing = IssueMilestone.objects.filter(issue=issue).first()
    if milestone_id is None:
        # Clearing one module cannot silently remove another module's value.
        if existing and existing.milestone.module_id != module.pk:
            raise PermissionDenied('Milestone scope unavailable')
        IssueMilestone.objects.filter(issue=issue).update(deleted_at=timezone.now())
        return None
    target = _milestone(module,milestone_id)
    if target.archived_at is not None:raise ValidationError('Unarchive the milestone before assigning issues')
    if existing:
        existing.milestone=target;existing.save();return existing
    return IssueMilestone.objects.create(project_id=module.project_id,workspace_id=module.workspace_id,
        issue=issue,milestone=target)


@transaction.atomic
def delete_milestone(actor, module_id, milestone_id):
    module = _scope(actor,module_id)
    row = _milestone(module,milestone_id)
    if IssueMilestone.objects.filter(milestone=row).exists():
        raise MilestoneConflict('Explicitly clear every issue assignment before deletion')
    ModuleMilestone.objects.filter(pk=row.pk).update(deleted_at=timezone.now())
