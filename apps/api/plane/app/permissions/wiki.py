# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework.permissions import BasePermission, SAFE_METHODS

from plane.app.permissions.base import ROLE
from plane.db.models import Page, WorkspaceMember

ADMIN = ROLE.ADMIN.value
MEMBER = ROLE.MEMBER.value
GUEST = ROLE.GUEST.value


class WorkspaceWikiPermission(BasePermission):
    """Workspace-scoped wiki pages (is_global=True). Independent of project Pages."""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False

        slug = view.kwargs.get("slug")
        page_id = view.kwargs.get("page_id")
        membership = WorkspaceMember.objects.filter(
            member=request.user,
            workspace__slug=slug,
            is_active=True,
        ).first()
        if not membership:
            return False

        role = membership.role

        if page_id:
            page = Page.objects.filter(id=page_id, workspace__slug=slug, is_global=True).first()
            if page is None:
                return False
            if page.owned_by_id == request.user.id:
                return self._action_allowed(request.method, role, owner=True)
            if page.access == Page.PRIVATE_ACCESS:
                return False

        return self._action_allowed(request.method, role, owner=False)

    def _action_allowed(self, method, role, owner):
        if method in SAFE_METHODS:
            return role in [ADMIN, MEMBER, GUEST]
        if method == "DELETE":
            return owner or role == ADMIN
        if method in ["POST", "PUT", "PATCH"]:
            return owner or role in [ADMIN, MEMBER]
        return False
