/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PageHead } from "@/components/core/page-title";
import { WikiShell } from "@/components/wiki/wiki-shell";

export default function WorkspaceWikiPage() {
  return (
    <>
      <PageHead title="Wiki" />
      <WikiShell>
        <div className="flex h-full items-center justify-center p-8">
          <div className="max-w-md text-center">
            <h2 className="text-18 font-semibold text-primary">Workspace wiki</h2>
            <p className="mt-2 text-13 text-placeholder">
              Company-wide docs live here, not inside a project. Public pages are visible to every workspace member.
              Private pages stay with you. Nested pages hang off a parent in the sidebar.
            </p>
          </div>
        </div>
      </WikiShell>
    </>
  );
}
