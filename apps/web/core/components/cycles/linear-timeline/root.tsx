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
import { cycleSortTime, formatRailDate } from "./metrics";

type Props = {
  cycleIds: string[];
  workspaceSlug: string;
  projectId: string;
};

export const LinearCyclesTimeline = observer(function LinearCyclesTimeline(props: Props) {
  const { cycleIds, workspaceSlug, projectId } = props;
  const { getCycleById } = useCycle();

  const orderedIds = [...new Set(cycleIds)].sort((a, b) => {
    const left = getCycleById(a);
    const right = getCycleById(b);
    if (!left || !right) return 0;
    return cycleSortTime(right) - cycleSortTime(left);
  });

  return (
    <ContentWrapper variant={ERowVariant.HUGGING} className="flex-row">
      <div className="h-full min-w-0 flex-1 overflow-y-auto px-4 py-2">
        {orderedIds.map((cycleId, index) => {
          const cycle = getCycleById(cycleId);
          const previous = index > 0 ? getCycleById(orderedIds[index - 1]) : undefined;
          const showRailDate =
            !!cycle?.start_date && formatRailDate(cycle.start_date) !== formatRailDate(previous?.start_date ?? null);
          return (
            <LinearCycleRow
              key={cycleId}
              cycleId={cycleId}
              workspaceSlug={workspaceSlug}
              projectId={projectId}
              showRailDate={showRailDate}
              isLast={index === orderedIds.length - 1}
            />
          );
        })}
      </div>
      <CyclePeekOverview projectId={projectId} workspaceSlug={workspaceSlug} />
    </ContentWrapper>
  );
});
