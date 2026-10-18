import type { EnvironmentEntry, Geometry, RegisteredSession } from "../api/types";
import { extentOf } from "../draw/environment";
import type { Extent } from "../draw/map";
import type { Fact } from "../ui/facts";
import type { Column } from "../ui/table";
import { counted } from "../ui/text";
import { formatStamp, stampWithSince } from "../ui/time";

const CM_PER_M = 100;
const DEGREES_PER_RADIAN = 180 / Math.PI;
const HALF_TURN = 180;
const FULL_TURN = 360;

const oneDecimal = (value: number) => value.toFixed(1);
// An angle in degrees to one decimal, a hair under zero written 0.0 and not -0.0.
const angleText = (radians: number) => (+(radians * DEGREES_PER_RADIAN).toFixed(1)).toFixed(1);

/** The parameters of an environment's yaml as facts, a nested group written as its name and the key, a list as its items. */
export function paramFacts(params: Record<string, unknown>, prefix = ""): Fact[] {
  return Object.entries(params).flatMap(([key, value]) =>
    value !== null && typeof value === "object" && !Array.isArray(value)
      ? paramFacts(value as Record<string, unknown>, `${prefix}${key} `)
      : [{ label: `${prefix}${key}`, value: Array.isArray(value) ? value.join(", ") : String(value) }]);
}

/** The extent holding every geometry, so all of them are drawn at one scale. */
export function sharedExtent(geometries: Geometry[]): Extent {
  const none = new Float64Array(0);
  const extents = geometries.map((geometry) => extentOf(geometry, none, none));
  return {
    x: [Math.min(...extents.map((e) => e.x[0])), Math.max(...extents.map((e) => e.x[1]))],
    y: [Math.min(...extents.map((e) => e.y[0])), Math.max(...extents.map((e) => e.y[1]))],
  };
}

export const rowId = (row: RegisteredSession): string => `${row.session_id}/${row.kind}`;

const scaleText = (r: RegisteredSession) =>
  r.scale_x === undefined ? oneDecimal(r.scale_px_per_m) : `${oneDecimal(r.scale_px_per_m)} (x ${oneDecimal(r.scale_x)}, y ${oneDecimal(r.scale_y!)})`;

/** The chip's text, how many warnings the session's build gave. */
export const warningsText = (r: RegisteredSession): string => String(r.warnings.length);

export const COLUMNS: readonly Column<RegisteredSession>[] = [
  { key: "session", label: "Session", value: (r) => r.session_id, text: (r) => r.session_id },
  { key: "kind", label: "Epoch", value: (r) => r.kind, text: (r) => r.kind },
  { key: "scale", label: "Scale, px per m", value: (r) => r.scale_px_per_m, text: scaleText, numeric: true },
  { key: "rotation", label: "Rotation, deg", value: (r) => r.rotation_rad, text: (r) => angleText(r.rotation_rad), numeric: true },
  { key: "led", label: "LED separation, cm", value: (r) => r.led_separation_m, text: (r) => oneDecimal(r.led_separation_m * CM_PER_M), numeric: true },
  {
    key: "offset", label: "LED offset, deg, r and n", value: (r) => r.led_offset_rad, numeric: true,
    text: (r) => `${angleText(r.led_offset_rad)}, r ${r.led_offset_r.toFixed(2)}, n ${r.led_offset_n}`,
  },
  { key: "built", label: "Built at", value: (r) => r.built_at, text: (r) => formatStamp(r.built_at) },
];

/** The warnings column, drawn as a chip beside the others, which the table still sorts on. */
export const WARNINGS: Column<RegisteredSession> = { key: "warnings", label: "Warnings", value: (r) => r.warnings.length, text: warningsText };

/** What the table sorts on: its columns and the warnings. */
export const SORTABLE: readonly Column<RegisteredSession>[] = [...COLUMNS, WARNINGS];

/** The hover text of a row: the session and its epoch, then each warning on a line of its own. */
export function rowTitle(row: RegisteredSession): string {
  return [`${row.session_id}, ${row.kind}`, ...row.warnings].join("\n");
}

/** What an expanded row adds to the columns. */
export function registrationFacts(row: RegisteredSession): Fact[] {
  return [
    { label: "frame flip", value: row.flip ? "yes" : "no" },
    { label: "frame offset", value: `${row.offset_m.map((m) => m.toFixed(3)).join(", ")} m` },
    { label: "built", value: stampWithSince(row.built_at) },
  ];
}

/** A range of numbers written low to high at the decimals given, one number when both ends round alike. */
function range(low: number, high: number, decimals: number): string {
  // Rounding first and writing after keeps a hair under zero from being written -0.0.
  const [from, to] = [low, high].map((value) => (+value.toFixed(decimals)).toFixed(decimals));
  return from === to ? from : `${from} to ${to}`;
}

const spanOf = (values: number[], decimals: number) => range(Math.min(...values), Math.max(...values), decimals);

/** The shortest arc holding the angles in degrees, from its start to its end counter-clockwise, the end running past 180 when the arc crosses it. */
export function circularRange(angles: number[]): { from: number; to: number } {
  const sorted = angles.map((angle) => ((angle % FULL_TURN) + FULL_TURN) % FULL_TURN).sort((a, b) => a - b);
  // The arc is what is left of the circle after its widest gap between neighbouring angles.
  let start = 0;
  let widest = -1;
  sorted.forEach((angle, i) => {
    const gap = i === 0 ? angle + FULL_TURN - sorted[sorted.length - 1] : angle - sorted[i - 1];
    if (gap > widest) [start, widest] = [i, gap];
  });
  const from = sorted[start];
  const last = sorted[(start + sorted.length - 1) % sorted.length];
  const shift = from > HALF_TURN ? FULL_TURN : 0;
  return { from: from - shift, to: (last >= from ? last : last + FULL_TURN) - shift };
}

/** The line over a table: how many sessions, the ranges of scale, rotation and LED separation over them, and how many carry a warning. Nothing else, no medians. */
export function rangesLine(sessions: RegisteredSession[], summary: EnvironmentEntry["summary"]): string {
  if (!sessions.length) return "";
  const rotation = circularRange(sessions.map((r) => r.rotation_rad * DEGREES_PER_RADIAN));
  return [
    counted(summary.n_sessions, "session"),
    `scale ${spanOf(sessions.map((r) => r.scale_px_per_m), 1)} px per m`,
    `rotation ${range(rotation.from, rotation.to, 1)} deg`,
    `LED separation ${spanOf(sessions.map((r) => r.led_separation_m * CM_PER_M), 1)} cm`,
    `${counted(summary.n_warned, "session")} with a warning`,
  ].join(", ");
}
