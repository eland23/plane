# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime

from django.db.models import Q
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions.wiki import WorkspaceWikiPermission
from plane.app.serializers.page import (
    PageBinaryUpdateSerializer,
    PageDetailSerializer,
    PageSerializer,
)
from plane.bgtasks.page_transaction_task import page_transaction
from plane.bgtasks.page_version_task import track_page_version
from plane.db.models import Page, Workspace
from plane.utils.error_codes import ERROR_CODES

from ..base import BaseViewSet
from .base import unarchive_archive_page_and_descendants


class WorkspaceWikiViewSet(BaseViewSet):
    serializer_class = PageSerializer
    model = Page
    permission_classes = [WorkspaceWikiPermission]
    search_fields = ["name"]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"), is_global=True)
            .filter(Q(owned_by=self.request.user) | Q(access=Page.PUBLIC_ACCESS))
            .select_related("workspace", "owned_by", "parent")
            .order_by("sort_order", "-created_at")
        )

    def _workspace(self, slug):
        return Workspace.objects.get(slug=slug)

    def _wiki_page(self, slug, page_id):
        return Page.objects.get(pk=page_id, workspace__slug=slug, is_global=True)

    def list(self, request, slug):
        queryset = self.get_queryset()
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        return Response(PageSerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    def create(self, request, slug):
        workspace = self._workspace(slug)
        parent_id = request.data.get("parent") or request.data.get("parent_id")
        if parent_id:
            self._wiki_page(slug, parent_id)

        page = Page.objects.create(
            name=request.data.get("name") or "Untitled",
            access=request.data.get("access", Page.PUBLIC_ACCESS),
            color=request.data.get("color", ""),
            parent_id=parent_id,
            is_locked=False,
            is_global=True,
            owned_by_id=request.user.id,
            workspace_id=workspace.id,
            description_html=request.data.get("description_html") or "<p></p>",
            description_json=request.data.get("description_json") or {},
            created_by_id=request.user.id,
            updated_by_id=request.user.id,
        )
        page_transaction.delay(
            new_description_html=page.description_html,
            old_description_html=None,
            page_id=str(page.id),
        )
        return Response(PageDetailSerializer(page).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, slug, page_id):
        page = self.get_queryset().filter(pk=page_id).first()
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PageDetailSerializer(page).data, status=status.HTTP_200_OK)

    def partial_update(self, request, slug, page_id):
        page = self._wiki_page(slug, page_id)
        if page.is_locked:
            return Response({"error": "Page is locked"}, status=status.HTTP_400_BAD_REQUEST)

        parent_id = request.data.get("parent", None)
        if parent_id:
            if str(parent_id) == str(page.id):
                return Response({"error": "A page cannot be its own parent"}, status=status.HTTP_400_BAD_REQUEST)
            self._wiki_page(slug, parent_id)

        if page.access != request.data.get("access", page.access) and page.owned_by_id != request.user.id:
            return Response(
                {"error": "Access cannot be updated since this page is owned by someone else"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PageDetailSerializer(page, data=request.data, partial=True)
        old_html = page.description_html
        if serializer.is_valid():
            serializer.save()
            if request.data.get("description_html"):
                page_transaction.delay(
                    new_description_html=request.data.get("description_html"),
                    old_description_html=old_html,
                    page_id=str(page_id),
                )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def lock(self, request, slug, page_id):
        page = self._wiki_page(slug, page_id)
        page.is_locked = True
        page.save(update_fields=["is_locked"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def unlock(self, request, slug, page_id):
        page = self._wiki_page(slug, page_id)
        page.is_locked = False
        page.save(update_fields=["is_locked"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def access(self, request, slug, page_id):
        page = self._wiki_page(slug, page_id)
        if page.owned_by_id != request.user.id:
            return Response(
                {"error": "Access cannot be updated since this page is owned by someone else"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        page.access = request.data.get("access", page.access)
        page.save(update_fields=["access"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def archive(self, request, slug, page_id):
        page = self._wiki_page(slug, page_id)
        unarchive_archive_page_and_descendants(page_id, datetime.now())
        return Response({"archived_at": str(datetime.now())}, status=status.HTTP_200_OK)

    def unarchive(self, request, slug, page_id):
        page = self._wiki_page(slug, page_id)
        if page.parent_id and page.parent and page.parent.archived_at:
            page.parent = None
            page.save(update_fields=["parent"])
        unarchive_archive_page_and_descendants(page_id, None)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy(self, request, slug, page_id):
        page = self._wiki_page(slug, page_id)
        if page.archived_at is None:
            return Response(
                {"error": "The page should be archived before deleting"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        Page.objects.filter(parent_id=page_id, workspace__slug=slug, is_global=True).update(parent=None)
        page.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceWikiDescriptionViewSet(BaseViewSet):
    permission_classes = [WorkspaceWikiPermission]

    def retrieve(self, request, slug, page_id):
        page = Page.objects.get(
            Q(owned_by=request.user) | Q(access=Page.PUBLIC_ACCESS),
            pk=page_id,
            workspace__slug=slug,
            is_global=True,
        )

        def stream_data():
            yield page.description_binary or b""

        response = StreamingHttpResponse(stream_data(), content_type="application/octet-stream")
        response["Content-Disposition"] = 'attachment; filename="page_description.bin"'
        return response

    def partial_update(self, request, slug, page_id):
        page = Page.objects.get(
            Q(owned_by=request.user) | Q(access=Page.PUBLIC_ACCESS),
            pk=page_id,
            workspace__slug=slug,
            is_global=True,
        )
        if page.is_locked:
            return Response(
                {"error_code": ERROR_CODES["PAGE_LOCKED"], "error_message": "PAGE_LOCKED"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if page.archived_at:
            return Response(
                {"error_code": ERROR_CODES["PAGE_ARCHIVED"], "error_message": "PAGE_ARCHIVED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_html = page.description_html
        serializer = PageBinaryUpdateSerializer(page, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            if request.data.get("description_html"):
                page_transaction.delay(
                    new_description_html=request.data.get("description_html"),
                    old_description_html=old_html,
                    page_id=str(page_id),
                )
                track_page_version.delay(
                    page_id=str(page_id),
                    existing_instance='{"description_html": null}',
                    user_id=request.user.id,
                )
            return Response({"message": "Updated successfully"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
