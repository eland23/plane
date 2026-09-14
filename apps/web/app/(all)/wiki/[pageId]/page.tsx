/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useParams } from "next/navigation";
import { WikiRootRedirect } from "@/components/wiki/wiki-root-redirect";

export default function WikiPageRedirectPage() {
  const { pageId } = useParams();
  return <WikiRootRedirect pageId={pageId?.toString()} />;
}
