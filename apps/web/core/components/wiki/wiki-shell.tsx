/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR, { mutate as mutateSWR } from "swr";
import { ChevronRight, FileText, Plus, Search } from "lucide-react";
import { Button } from "@plane/propel/button";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { cn } from "@plane/utils";
import { type TWikiPage, workspaceWikiService } from "@/services/page/workspace-wiki.service";

type Tab = "public" | "private" | "archived";

const wikiKey = (slug: string, search: string) => `WORKSPACE_WIKI_${slug}_${search}`;

const matchesTab = (page: TWikiPage, tab: Tab) => {
  if (tab === "archived") return Boolean(page.archived_at);
  if (page.archived_at) return false;
  if (tab === "private") return page.access === 1;
  return page.access === 0;
};

const buildTree = (pages: TWikiPage[], tab: Tab) => {
  const visible = pages.filter((page) => matchesTab(page, tab));
  const byParent = new Map<string | null, TWikiPage[]>();
  visible.forEach((page) => {
    const key = page.parent ?? null;
    const list = byParent.get(key) ?? [];
    list.push(page);
    byParent.set(key, list);
  });
  return byParent;
};

function WikiTreeNodes({
  parentId,
  byParent,
  workspaceSlug,
  selectedId,
  depth = 0,
}: {
  parentId: string | null;
  byParent: Map<string | null, TWikiPage[]>;
  workspaceSlug: string;
  selectedId?: string;
  depth?: number;
}) {
  const router = useRouter();
  const children = byParent.get(parentId) ?? [];
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  return (
    <>
      {children.map((page) => {
        const nested = byParent.get(page.id) ?? [];
        const isCollapsed = collapsed[page.id];
        return (
          <div key={page.id}>
            <div
              className={cn(
                "group flex items-center gap-1 rounded-sm px-2 py-1 text-13 hover:bg-layer-transparent-hover",
                selectedId === page.id && "bg-layer-transparent-hover text-primary"
              )}
              style={{ paddingLeft: 8 + depth * 12 }}
            >
              {nested.length > 0 ? (
                <button
                  type="button"
                  className="text-placeholder"
                  onClick={() => setCollapsed((prev) => ({ ...prev, [page.id]: !prev[page.id] }))}
                  aria-label={isCollapsed ? "Expand page" : "Collapse page"}
                >
                  <ChevronRight className={cn("size-3.5 transition-transform", !isCollapsed && "rotate-90")} />
                </button>
              ) : (
                <span className="w-3.5" />
              )}
              <button
                type="button"
                className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                onClick={() => router.push(`/${workspaceSlug}/wiki/${page.id}`)}
              >
                <FileText className="size-3.5 shrink-0 text-tertiary" />
                <span className="truncate">{page.name || "Untitled"}</span>
              </button>
              <button
                type="button"
                className="hidden rounded-sm p-0.5 text-placeholder hover:bg-layer-1 group-hover:block"
                aria-label="Create nested page"
                onClick={async (event) => {
                  event.stopPropagation();
                  try {
                    const created = await workspaceWikiService.create(workspaceSlug, {
                      name: "Untitled",
                      parent: page.id,
                      access: page.access,
                    });
                    await mutateSWR((key) => typeof key === "string" && key.startsWith(`WORKSPACE_WIKI_${workspaceSlug}`));
                    router.push(`/${workspaceSlug}/wiki/${created.id}`);
                  } catch {
                    setToast({ type: TOAST_TYPE.ERROR, title: "Could not create page" });
                  }
                }}
              >
                <Plus className="size-3.5" />
              </button>
            </div>
            {!isCollapsed && nested.length > 0 && (
              <WikiTreeNodes
                parentId={page.id}
                byParent={byParent}
                workspaceSlug={workspaceSlug}
                selectedId={selectedId}
                depth={depth + 1}
              />
            )}
          </div>
        );
      })}
    </>
  );
}

export function WikiShell({ children, selectedId }: { children: ReactNode; selectedId?: string }) {
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("public");
  const [search, setSearch] = useState("");
  const { data: pages = [], mutate } = useSWR(slug ? wikiKey(slug, search) : null, () =>
    workspaceWikiService.list(slug, search)
  );

  const byParent = useMemo(() => buildTree(pages, tab), [pages, tab]);
  const roots = byParent.get(null) ?? [];

  const createPage = async () => {
    try {
      const created = await workspaceWikiService.create(slug, {
        name: "Untitled",
        access: tab === "private" ? 1 : 0,
      });
      await mutate();
      router.push(`/${slug}/wiki/${created.id}`);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not create wiki page" });
    }
  };

  return (
    <div className="flex h-full min-h-0 w-full">
      <aside className="flex w-72 shrink-0 flex-col border-r border-subtle bg-layer-1">
        <div className="flex items-center justify-between gap-2 px-3 py-3">
          <h1 className="text-14 font-semibold text-primary">Wiki</h1>
          <Button variant="primary" size="sm" onClick={createPage}>
            New page
          </Button>
        </div>
        <div className="px-3 pb-2">
          <div className="flex items-center gap-1.5 rounded-md border border-subtle px-2 py-1.5 text-13 text-tertiary">
            <Search className="size-3.5" />
            <input
              className="w-full bg-transparent outline-none placeholder:text-placeholder"
              placeholder="Search wiki"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
        </div>
        <div className="flex gap-1 px-3 pb-2">
          {(["public", "private", "archived"] as Tab[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                "rounded-sm px-2 py-1 text-12 capitalize",
                tab === key ? "bg-layer-2 text-primary" : "text-placeholder hover:text-primary"
              )}
            >
              {key}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-1 pb-4">
          {roots.length === 0 ? (
            <p className="px-3 py-6 text-13 text-placeholder">
              Workspace wiki is independent of project Pages. Create a page to start the knowledge base.
            </p>
          ) : (
            <WikiTreeNodes parentId={null} byParent={byParent} workspaceSlug={slug} selectedId={selectedId} />
          )}
        </div>
      </aside>
      <div className="min-w-0 flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
