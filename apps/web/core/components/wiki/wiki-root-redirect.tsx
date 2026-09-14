/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { LogoSpinner } from "@/components/common/logo-spinner";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUser } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";

type Props = {
  pageId?: string;
};

export const WikiRootRedirect = observer(function WikiRootRedirect({ pageId }: Props) {
  const router = useAppRouter();
  const { data: currentUser, isLoading: isUserLoading } = useUser();
  const { getWorkspaceRedirectionUrl, loader: workspacesLoader } = useWorkspace();

  useEffect(() => {
    if (isUserLoading || workspacesLoader || !currentUser) return;
    const workspacePath = getWorkspaceRedirectionUrl();
    if (workspacePath === "/create-workspace") {
      router.replace(workspacePath);
      return;
    }
    router.replace(pageId ? `${workspacePath}/wiki/${pageId}` : `${workspacePath}/wiki`);
  }, [currentUser, getWorkspaceRedirectionUrl, isUserLoading, pageId, router, workspacesLoader]);

  return (
    <AuthenticationWrapper>
      <div className="grid h-full place-items-center">
        <LogoSpinner />
      </div>
    </AuthenticationWrapper>
  );
});
