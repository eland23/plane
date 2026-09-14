/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Archive, Lock, Trash2, Unlock } from "lucide-react";
import { Button } from "@plane/propel/button";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { workspaceWikiService } from "@/services/page/workspace-wiki.service";

export function WikiEditor() {
  const { workspaceSlug, pageId } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const id = pageId?.toString() ?? "";
  const router = useRouter();
  const { data: page, mutate } = useSWR(slug && id ? `WORKSPACE_WIKI_PAGE_${id}` : null, () =>
    workspaceWikiService.retrieve(slug, id)
  );
  const [name, setName] = useState("");
  const [html, setHtml] = useState("");

  useEffect(() => {
    if (!page) return;
    setName(page.name);
    setHtml(page.description_html ?? "<p></p>");
  }, [page]);

  if (!page) {
    return <div className="p-8 text-13 text-placeholder">Loading page…</div>;
  }

  const saveTitle = async () => {
    if (name === page.name) return;
    try {
      await workspaceWikiService.update(slug, id, { name });
      await mutate();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not rename page" });
    }
  };

  const saveBody = async () => {
    if ((page.description_html ?? "<p></p>") === html) return;
    try {
      await workspaceWikiService.updateDescription(slug, id, html);
      await mutate();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not save page" });
    }
  };

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4 px-8 py-6">
      <div className="flex items-start justify-between gap-3">
        <input
          className="w-full bg-transparent text-24 font-semibold text-primary outline-none"
          value={name}
          disabled={page.is_locked || Boolean(page.archived_at)}
          onChange={(event) => setName(event.target.value)}
          onBlur={saveTitle}
        />
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              await workspaceWikiService.setAccess(slug, id, page.access === 0 ? 1 : 0);
              await mutate();
            }}
          >
            {page.access === 0 ? "Public" : "Private"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              try {
                if (page.is_locked) await workspaceWikiService.unlock(slug, id);
                else await workspaceWikiService.lock(slug, id);
                await mutate();
              } catch {
                setToast({ type: TOAST_TYPE.ERROR, title: "Could not update lock" });
              }
            }}
          >
            {page.is_locked ? <Unlock className="size-3.5" /> : <Lock className="size-3.5" />}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              if (page.archived_at) await workspaceWikiService.unarchive(slug, id);
              else await workspaceWikiService.archive(slug, id);
              await mutate();
              router.push(`/${slug}/wiki`);
            }}
          >
            <Archive className="size-3.5" />
          </Button>
          {page.archived_at && (
            <Button
              variant="error-fill"
              size="sm"
              onClick={async () => {
                await workspaceWikiService.remove(slug, id);
                router.push(`/${slug}/wiki`);
              }}
            >
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
      </div>
      <textarea
        className="min-h-[28rem] w-full resize-y rounded-md border border-subtle bg-surface-1 p-4 text-14 text-primary outline-none"
        value={html}
        disabled={page.is_locked || Boolean(page.archived_at)}
        onChange={(event) => setHtml(event.target.value)}
        onBlur={saveBody}
      />
      <p className="text-12 text-placeholder">
        Workspace wiki. This page is not a project Page. HTML is stored on the existing Community `pages` table with
        `is_global=true`.
      </p>
    </div>
  );
}
