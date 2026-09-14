/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useParams } from "next/navigation";
import { PageHead } from "@/components/core/page-title";
import { WikiEditor } from "@/components/wiki/wiki-editor";
import { WikiShell } from "@/components/wiki/wiki-shell";

export default function WorkspaceWikiDetailPage() {
  const { pageId } = useParams();
  return (
    <>
      <PageHead title="Wiki" />
      <WikiShell selectedId={pageId?.toString()}>
        <WikiEditor />
      </WikiShell>
    </>
  );
}
