/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { parseISO } from "date-fns";
import type { ICycle, TCycleProgress } from "@plane/types";
import { getDate } from "@plane/utils";

type Point = {
  t: number;
  scope: number;
  started: number;
  completed: number;
};

const COLORS = {
  scope: "currentColor",
  started: "#E2B714",
  completed: "#5E6AD2",
};

const asProgress = (value: unknown): TCycleProgress[] => {
  if (!Array.isArray(value)) return [];
  return value.filter((row) => row && typeof row === "object" && "date" in row) as TCycleProgress[];
};

const buildPoints = (cycle: ICycle): Point[] => {
  const progress = asProgress(cycle.progress);
  if (progress.length > 1) {
    return progress
      .map((row) => {
        const date = getDate(row.date);
        if (!date) return null;
        return {
          t: date.getTime(),
          scope: Number(row.scope ?? 0),
          started: Number(row.started ?? 0),
          completed: Number(row.completed ?? 0),
        };
      })
      .filter((p): p is Point => p !== null);
  }

  const start = getDate(cycle.start_date);
  const end = getDate(cycle.end_date) ?? new Date();
  const now = new Date();
  const mid = now < end && (!start || now > start) ? now : end;
  if (!start) return [];

  const scope = Math.max(0, (cycle.total_issues || 0) - (cycle.cancelled_issues || 0));
  const started = cycle.started_issues || 0;
  const completed = cycle.completed_issues || 0;

  return [
    { t: start.getTime(), scope, started: 0, completed: 0 },
    { t: mid.getTime(), scope, started, completed },
    { t: end.getTime(), scope, started, completed },
  ];
};

const polyline = (points: Point[], key: keyof Omit<Point, "t">, x: (t: number) => number, y: (v: number) => number) =>
  points.map((p) => `${x(p.t).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");

export function LinearBurnupChart({ cycle }: { cycle: ICycle }) {
  const points = buildPoints(cycle);
  if (points.length < 2) return null;

  const width = 640;
  const height = 168;
  const pad = { l: 8, r: 12, t: 10, b: 18 };
  const minT = Math.min(...points.map((p) => p.t));
  const maxT = Math.max(...points.map((p) => p.t));
  const maxY = Math.max(1, ...points.flatMap((p) => [p.scope, p.started, p.completed]));
  const x = (t: number) => pad.l + ((t - minT) / Math.max(1, maxT - minT)) * (width - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / maxY) * (height - pad.t - pad.b);

  const now = Date.now();
  const hatchStart = Math.min(Math.max(now, minT), maxT);
  const futureX = x(hatchStart);

  const startLabel = cycle.start_date ? parseISO(cycle.start_date) : null;
  const endLabel = cycle.end_date ? parseISO(cycle.end_date) : null;

  return (
    <div className="w-full text-tertiary">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full" role="img" aria-label="Cycle scope, started, and completed">
        <defs>
          <pattern id="linear-cycle-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" strokeOpacity="0.18" strokeWidth="2" />
          </pattern>
        </defs>
        {hatchStart < maxT && (
          <rect x={futureX} y={pad.t} width={width - pad.r - futureX} height={height - pad.t - pad.b} fill="url(#linear-cycle-hatch)" />
        )}
        <polyline fill="none" stroke={COLORS.scope} strokeWidth="1.5" strokeOpacity="0.55" points={polyline(points, "scope", x, y)} />
        <polyline fill="none" stroke={COLORS.started} strokeWidth="2" points={polyline(points, "started", x, y)} />
        <polyline fill="none" stroke={COLORS.completed} strokeWidth="2" points={polyline(points, "completed", x, y)} />
      </svg>
      <div className="mt-1 flex items-center justify-between px-1 text-[11px] text-placeholder">
        <span>{startLabel ? startLabel.toLocaleDateString(undefined, { month: "short", day: "numeric" }) : ""}</span>
        <span>{endLabel ? endLabel.toLocaleDateString(undefined, { month: "short", day: "numeric" }) : ""}</span>
      </div>
    </div>
  );
}
