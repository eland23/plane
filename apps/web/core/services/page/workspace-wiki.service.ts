/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TWikiPage = {
  id: string;
  name: string;
  access: 0 | 1;
  parent: string | null;
  is_locked: boolean;
  archived_at: string | null;
  owned_by: string;
  workspace: string;
  created_at: string;
  updated_at: string;
  description_html?: string;
};

export class WorkspaceWikiService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async list(workspaceSlug: string, search?: string): Promise<TWikiPage[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/`, {
      params: search ? { search } : {},
    }).then((response) => response?.data);
  }

  async retrieve(workspaceSlug: string, pageId: string): Promise<TWikiPage> {
    return this.get(`/api/workspaces/${workspaceSlug}/pages/${pageId}/`).then((response) => response?.data);
  }

  async create(workspaceSlug: string, data: Partial<TWikiPage>): Promise<TWikiPage> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/`, data).then((response) => response?.data);
  }

  async update(workspaceSlug: string, pageId: string, data: Partial<TWikiPage>): Promise<TWikiPage> {
    return this.patch(`/api/workspaces/${workspaceSlug}/pages/${pageId}/`, data).then((response) => response?.data);
  }

  async updateDescription(
    workspaceSlug: string,
    pageId: string,
    data: {
      description_html: string;
      description_json?: object;
    }
  ): Promise<void> {
    return this.patch(`/api/workspaces/${workspaceSlug}/pages/${pageId}/description/`, data).then(
      (response) => response?.data
    );
  }

  async archive(workspaceSlug: string, pageId: string): Promise<{ archived_at: string }> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/archive/`).then((response) => response?.data);
  }

  async unarchive(workspaceSlug: string, pageId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/pages/${pageId}/archive/`).then((response) => response?.data);
  }

  async remove(workspaceSlug: string, pageId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/pages/${pageId}/`).then((response) => response?.data);
  }

  async lock(workspaceSlug: string, pageId: string): Promise<void> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/lock/`).then((response) => response?.data);
  }

  async unlock(workspaceSlug: string, pageId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/pages/${pageId}/lock/`).then((response) => response?.data);
  }

  async setAccess(workspaceSlug: string, pageId: string, access: 0 | 1): Promise<void> {
    return this.post(`/api/workspaces/${workspaceSlug}/pages/${pageId}/access/`, { access }).then(
      (response) => response?.data
    );
  }
}

export const workspaceWikiService = new WorkspaceWikiService();
