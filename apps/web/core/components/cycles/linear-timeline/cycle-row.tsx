/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { observer } from "mobx-react";
import { Triangle } from "lucide-react";
import type { ICycle } from "@plane/types";
import { cn } from "@plane/utils";
import useCyclesDetails from "@/components/cycles/active-cycle/use-cycles-details";
import { CycleQuickActions } from "@/components/cycles/quick-actions";
import { useCycle } from "@/hooks/store/use-cycle";
import { useAppRouter } from "@/hooks/use-app-router";
import { LinearBurnupChart } from "./burnup-chart";
import { formatRailDate, linearCycleMetrics } from "./metrics";

type Props = {
  cycleId: string;
  workspaceSlug: string;
  projectId: string;
  showRailDate: boolean;
  isLast: boolean;
};

const Stat = ({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "danger" | "warning" | "success" | "muted";
}) => (
  <span className="inline-flex items-center gap-1.5 text-[12px] text-tertiary">
    <span>{label}</span>
    <Triangle
      className={cn("size-2.5 fill-current", {
        "text-placeholder": !tone || tone === "muted",
        "text-red-500": tone === "danger",
        "text-amber-400": tone === "warning",
        "text-emerald-400": tone === "success",
      })}
    />
    <span className="tabular-nums text-secondary">{value}</span>
  </span>
);

export const LinearCycleRow = observer(function LinearCycleRow(props: Props) {
  const { cycleId, workspaceSlug, projectId, showRailDate, isLast } = props;
  const parentRef = useRef<HTMLDivElement>(null);
  const router = useAppRouter();
  const { getCycleById } = useCycle();
  const listed = getCycleById(cycleId) as ICycle | undefined;
  const isCurrent = listed ? linearCycleMetrics(listed).kind === "current" : false;
  const { cycle: detailed } = useCyclesDetails({
    workspaceSlug,
    projectId,
    cycleId: isCurrent ? cycleId : null,
  });
  const cycle = (detailed ?? listed) as ICycle | undefined;

  if (!cycle) return null;

  const metrics = linearCycleMetrics(cycle);
  const href = `/${workspaceSlug}/projects/${projectId}/cycles/${cycle.id}`;

  return (
    <div className="relative flex min-h-[52px]" ref={parentRef}>
      <div className="relative w-16 shrink-0">
        {!isLast && <div className="absolute top-4 bottom-0 left-[11px] w-px bg-subtle" />}
        <div className="absolute top-3.5 left-[7px] size-2 rounded-full border border-subtle bg-layer-1" />
        {showRailDate && (
          <div className="absolute top-11 left-0 w-14 text-[11px] leading-tight text-placeholder">
            {formatRailDate(cycle.start_date)}
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1 border-b border-subtle">
        <button
          type="button"
          onClick={() => router.push(href)}
          className={cn(
            "flex w-full items-center justify-between gap-4 py-3 pr-2 text-left hover:bg-layer-2/40",
            isCurrent && "items-start"
          )}
        >
          <div className="min-w-0">
            <div className="truncate text-[13px] font-medium text-primary">{cycle.name}</div>
            {isCurrent && (
              <div className="mt-3 max-w-xl">
                <LinearBurnupChart cycle={cycle} />
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-tertiary">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2 rounded-[1px] bg-tertiary/70" />
                    Scope
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2 rounded-[1px] bg-[#E2B714]" />
                    Started
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2 rounded-[1px] bg-[#5E6AD2]" />
                    Completed
                  </span>
                </div>
              </div>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1 pt-0.5">
            <div className="flex items-center gap-3">
              {metrics.kind === "completed" ? (
                <>
                  <Stat label="" value={`${metrics.successPercent}% success`} tone={metrics.successPercent >= 70 ? "success" : "danger"} />
                  <Stat label="" value={`${metrics.completed} completed`} />
                  <Stat label="" value={`${metrics.scope} scope`} />
                </>
              ) : (
                <>
                  <Stat
                    label=""
                    value={`${metrics.capacityPercent}% of capacity`}
                    tone={isCurrent ? "warning" : "muted"}
                  />
                  <Stat label="" value={`${metrics.scope} scope`} tone={isCurrent ? "danger" : "muted"} />
                </>
              )}
              {isCurrent && (
                <>
                  <Stat label="Started" value={`${metrics.started}`} tone="warning" />
                  <Stat label="Completed" value={`${metrics.completed}`} />
                </>
              )}
            </div>
          </div>
        </button>
        <div
          className="absolute top-2.5 right-1 z-[2] hidden md:block"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <CycleQuickActions
            parentRef={parentRef}
            cycleId={cycleId}
            projectId={projectId}
            workspaceSlug={workspaceSlug}
          />
        </div>
      </div>
    </div>
  );
});
