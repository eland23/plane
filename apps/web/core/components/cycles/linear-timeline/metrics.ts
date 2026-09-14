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
