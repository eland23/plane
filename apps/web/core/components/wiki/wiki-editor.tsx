/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { debounce } from "lodash-es";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Archive, Lock, Trash2, Unlock } from "lucide-react";
import type { EditorRefApi } from "@plane/editor";
import { Button } from "@plane/propel/button";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { EFileAssetType } from "@plane/types";
import { cn } from "@plane/utils";
import { DocumentEditor } from "@/components/editor/document/editor";
import { PageContentLoader } from "@/components/pages/loaders/page-content-loader";
import { PageEditorTitle } from "@/components/pages/editor/title";
import { PageToolbar } from "@/components/pages/editor/toolbar";
import { useEditorAsset } from "@/hooks/store/use-editor-asset";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { usePageFilters } from "@/hooks/use-page-filters";
import { WorkspaceService } from "@/services/workspace.service";
import { workspaceWikiService } from "@/services/page/workspace-wiki.service";

const workspaceService = new WorkspaceService();

export function WikiEditor() {
  const { workspaceSlug, pageId } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const id = pageId?.toString() ?? "";
  const router = useRouter();
  const editorRef = useRef<EditorRefApi>(null);
  const [editorReady, setEditorReady] = useState(false);
  const [name, setName] = useState("");
  const { getWorkspaceBySlug } = useWorkspace();
  const { uploadEditorAsset, duplicateEditorAsset } = useEditorAsset();
  const { fontSize, fontStyle, isFullWidth } = usePageFilters();
  const workspaceId = getWorkspaceBySlug(slug)?.id ?? "";

  const { data: page, mutate } = useSWR(slug && id ? `WORKSPACE_WIKI_PAGE_${id}` : null, () =>
    workspaceWikiService.retrieve(slug, id)
  );

  useEffect(() => {
    setName(page?.name ?? "");
    setEditorReady(false);
  }, [page?.id, page?.name]);

  const readOnly = Boolean(page?.is_locked || page?.archived_at);

  const persistDescription = useMemo(
    () =>
      debounce(async (html: string, json: object) => {
        if (!slug || !id || readOnly) return;
        try {
          const document = editorRef.current?.getDocument();
          await workspaceWikiService.updateDescription(slug, id, {
            description_html: html,
            description_json: json,
            description_binary: encodeBinary(document?.binary ?? null),
          });
        } catch {
          setToast({ type: TOAST_TYPE.ERROR, title: "Could not save page" });
        }
      }, 800),
    [id, readOnly, slug]
  );

  useEffect(
    () => () => {
      persistDescription.flush();
    },
    [persistDescription]
  );

  const persistTitle = useMemo(
    () =>
      debounce(async (title: string) => {
        if (!slug || !id || readOnly) return;
        try {
          await workspaceWikiService.update(slug, id, { name: title });
        } catch {
          setToast({ type: TOAST_TYPE.ERROR, title: "Could not rename page" });
        }
      }, 400),
    [id, readOnly, slug]
  );

  const searchMentionCallback = useCallback(
    async (payload: Parameters<typeof workspaceService.searchEntity>[1]) =>
      workspaceService.searchEntity(slug, payload),
    [slug]
  );

  const uploadFile = useCallback(
    async (blockId: string, file: File) => {
      const { asset_id } = await uploadEditorAsset({
        blockId,
        data: {
          entity_identifier: id,
          entity_type: EFileAssetType.PAGE_DESCRIPTION,
        },
        file,
        workspaceSlug: slug,
      });
      return asset_id;
    },
    [id, slug, uploadEditorAsset]
  );

  const duplicateFile = useCallback(
    async (assetId: string) => {
      const { asset_id } = await duplicateEditorAsset({
        assetId,
        entityId: id,
        entityType: EFileAssetType.PAGE_DESCRIPTION,
        workspaceSlug: slug,
      });
      return asset_id;
    },
    [duplicateEditorAsset, id, slug]
  );

  const displayConfig = useMemo(
    () => ({
      fontSize,
      fontStyle,
      wideLayout: isFullWidth,
    }),
    [fontSize, fontStyle, isFullWidth]
  );

  const blockWidthClassName = cn(
    "mx-auto block w-full max-w-[720px] bg-transparent transition-all duration-200 ease-in-out",
    {
      "max-w-[1152px]": isFullWidth,
    }
  );

  if (!page) {
    return <PageContentLoader className={blockWidthClassName} />;
  }

  return (
    <div className="relative flex size-full flex-col overflow-hidden">
      <div className="flex min-h-[52px] items-center justify-between gap-2 border-b border-subtle px-page-x">
        <div className="min-w-0 flex-1 overflow-x-auto">
          {editorReady && editorRef.current && !readOnly && <PageToolbar editorRef={editorRef.current} />}
        </div>
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
      <div className="vertical-scrollbar relative size-full overflow-y-auto">
        <div className={cn(blockWidthClassName, "px-page-x pt-6")}>
          <PageEditorTitle
            editorRef={editorRef.current}
            readOnly={readOnly}
            title={name}
            updateTitle={(title) => {
              setName(title);
              persistTitle(title);
            }}
          />
          {readOnly ? (
            <DocumentEditor
              key={id}
              editable={false}
              id={id}
              value={page.description_html || "<p></p>"}
              workspaceId={workspaceId}
              workspaceSlug={slug}
              displayConfig={displayConfig}
              containerClassName="h-full p-0 pb-64"
              handleEditorReady={setEditorReady}
              ref={editorRef}
            />
          ) : (
            <DocumentEditor
              key={id}
              editable
              id={id}
              value={page.description_html || "<p></p>"}
              workspaceId={workspaceId}
              workspaceSlug={slug}
              displayConfig={displayConfig}
              containerClassName="h-full p-0 pb-64"
              handleEditorReady={setEditorReady}
              ref={editorRef}
              searchMentionCallback={searchMentionCallback}
              uploadFile={uploadFile}
              duplicateFile={duplicateFile}
              onChange={(json, html) => persistDescription(html, json)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function encodeBinary(binary: Uint8Array | null): string {
  if (!binary || binary.length === 0) return "";
  let result = "";
  const chunk = 0x8000;
  for (let index = 0; index < binary.length; index += chunk) {
    result += String.fromCharCode(...binary.subarray(index, index + chunk));
  }
  return btoa(result);
}
