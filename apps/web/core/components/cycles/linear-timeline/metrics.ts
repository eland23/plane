/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { format, parseISO } from "date-fns";
import { isEmpty } from "lodash-es";
import type { ICycle, TCycleGroups, TProgressSnapshot } from "@plane/types";

export type TLinearCycleKind = TCycleGroups | "planned";

export type TLinearCycleMetrics = {
  kind: TLinearCycleKind;
  scope: number;
  started: number;
  completed: number;
  successPercent: number;
  capacityPercent: number;
};

const snapshotOf = (cycle: ICycle): TProgressSnapshot => {
  const snap = cycle.progress_snapshot;
  return snap && !isEmpty(snap) ? snap : cycle;
};

export const linearCycleKind = (cycle: ICycle): TLinearCycleKind => {
  const status = cycle.status ? (cycle.status.toLocaleLowerCase() as TCycleGroups) : "draft";
  if (status === "draft") return "planned";
  return status;
};

export const linearCycleMetrics = (cycle: ICycle): TLinearCycleMetrics => {
  const details = snapshotOf(cycle);
  const cancelled = details.cancelled_issues || 0;
  const scope = Math.max(0, (details.total_issues || 0) - cancelled);
  const started = details.started_issues || 0;
  const completed = details.completed_issues || 0;
  const successPercent = scope > 0 ? Math.round((completed / scope) * 100) : 0;
  // Capacity is estimate-points completion when the cycle has estimates; otherwise completed/scope.
  const estimateTotal = details.total_estimate_points || 0;
  const estimateDone = details.completed_estimate_points || 0;
  const capacityPercent =
    estimateTotal > 0 ? Math.round((estimateDone / estimateTotal) * 100) : scope > 0 ? successPercent : 0;

  return {
    kind: linearCycleKind(cycle),
    scope,
    started,
    completed,
    successPercent,
    capacityPercent,
  };
};

export const formatRailDate = (value: string | null): string => {
  if (!value) return "";
  try {
    return format(parseISO(value), "MMM d");
  } catch {
    return "";
  }
};

export const cycleSortTime = (cycle: ICycle): number => {
  if (cycle.start_date) return Date.parse(cycle.start_date);
  if (cycle.end_date) return Date.parse(cycle.end_date);
  return Date.parse(cycle.created_at ?? "") || 0;
};

export const kindLabel = (kind: TLinearCycleKind): string => {
  if (kind === "current") return "Current";
  if (kind === "upcoming") return "Upcoming";
  if (kind === "completed") return "Completed";
  return "Planned";
};

export const LINEAR_CYCLE_GROUP_ORDER: TLinearCycleKind[] = ["current", "upcoming", "planned", "completed"];

export const groupCycleIds = (
  cycleIds: string[],
  getCycle: (id: string) => ICycle | undefined
): { kind: TLinearCycleKind; ids: string[] }[] => {
  const buckets: Record<TLinearCycleKind, string[]> = {
    current: [],
    upcoming: [],
    planned: [],
    completed: [],
  };
  const seen = new Set<string>();
  for (const id of cycleIds) {
    if (seen.has(id)) continue;
    seen.add(id);
    const cycle = getCycle(id);
    if (!cycle) continue;
    buckets[linearCycleKind(cycle)].push(id);
  }

  const byStart = (direction: 1 | -1) => (leftId: string, rightId: string) => {
    const left = getCycle(leftId);
    const right = getCycle(rightId);
    if (!left || !right) return 0;
    return direction * (cycleSortTime(left) - cycleSortTime(right));
  };

  buckets.upcoming.sort(byStart(1));
  buckets.planned.sort(byStart(1));
  buckets.completed.sort(byStart(-1));

  return LINEAR_CYCLE_GROUP_ORDER.filter((kind) => buckets[kind].length > 0).map((kind) => ({
    kind,
    ids: buckets[kind],
  }));
};
