/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { ContentWrapper, ERowVariant } from "@plane/ui";
import { CyclePeekOverview } from "@/components/cycles/cycle-peek-overview";
import { useCycle } from "@/hooks/store/use-cycle";
import { LinearCycleRow } from "./cycle-row";
import { formatRailDate, groupCycleIds, kindLabel } from "./metrics";

type Props = {
  cycleIds: string[];
  workspaceSlug: string;
  projectId: string;
};

export const LinearCyclesTimeline = observer(function LinearCyclesTimeline(props: Props) {
  const { cycleIds, workspaceSlug, projectId } = props;
  const { getCycleById } = useCycle();
  const groups = groupCycleIds(cycleIds, getCycleById);
  const flatIds = groups.flatMap((group) => group.ids);

  return (
    <ContentWrapper variant={ERowVariant.HUGGING} className="flex-row">
      <div className="h-full min-w-0 flex-1 overflow-y-auto px-4 py-2">
        {groups.map((group) => (
          <section key={group.kind} className="mb-1">
            <h2 className="sticky top-0 z-[1] bg-surface-1 py-2 pl-16 text-[12px] font-medium tracking-wide text-placeholder uppercase">
              {kindLabel(group.kind)}
            </h2>
            {group.ids.map((cycleId) => {
              const index = flatIds.indexOf(cycleId);
              const cycle = getCycleById(cycleId);
              const previous = index > 0 ? getCycleById(flatIds[index - 1]) : undefined;
              const showRailDate =
                !!cycle?.start_date && formatRailDate(cycle.start_date) !== formatRailDate(previous?.start_date ?? null);
              return (
                <LinearCycleRow
                  key={cycleId}
                  cycleId={cycleId}
                  workspaceSlug={workspaceSlug}
                  projectId={projectId}
                  showRailDate={showRailDate}
                  isLast={index === flatIds.length - 1}
                />
              );
            })}
          </section>
        ))}
      </div>
      <CyclePeekOverview projectId={projectId} workspaceSlug={workspaceSlug} />
    </ContentWrapper>
  );
});
