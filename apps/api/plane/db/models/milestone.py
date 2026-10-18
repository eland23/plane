# Copyright (c) 2026 Plane contributors
# SPDX-License-Identifier: AGPL-3.0-only
from django.db import models
from .project import ProjectBaseModel


class ModuleMilestone(ProjectBaseModel):
    module = models.ForeignKey('db.Module', on_delete=models.PROTECT, related_name='milestones')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='planned', choices=[
        ('planned','Planned'), ('completed','Completed'), ('cancelled','Cancelled')])
    sort_order = models.FloatField(default=65535)
    archived_at = models.DateTimeField(null=True, blank=True)
    external_source = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'module_milestones'
        ordering = ('sort_order','id')
        constraints = [
            models.UniqueConstraint(fields=['workspace','external_source','external_id'],
                name='milestone_source_identity_unique'),
            models.CheckConstraint(condition=(models.Q(external_source__isnull=True,external_id__isnull=True)
                | (models.Q(external_source__isnull=False,external_id__isnull=False)
                    & ~models.Q(external_source='') & ~models.Q(external_id=''))),
                name='milestone_source_identity_complete'),
            models.CheckConstraint(condition=models.Q(status__in=['planned','completed','cancelled']),
                name='milestone_status_valid'),
        ]


class IssueMilestone(ProjectBaseModel):
    issue = models.ForeignKey('db.Issue', on_delete=models.CASCADE, related_name='milestone_assignments')
    milestone = models.ForeignKey(ModuleMilestone, on_delete=models.PROTECT, related_name='issue_assignments')

    class Meta:
        db_table = 'issue_milestones'
        constraints = [models.UniqueConstraint(fields=['issue'],condition=models.Q(deleted_at__isnull=True),
            name='issue_single_active_milestone')]
