import { expect, test } from "vitest";
import type { Geometry, RegisteredSession } from "../../src/api/types";
import { circularRange, COLUMNS, paramFacts, rangesLine, registrationFacts, rowTitle, sharedExtent, SORTABLE, WARNINGS } from "../../src/pages/environments-view";
import { sortRows } from "../../src/ui/table";

const RAD = Math.PI / 180;

function registration(session_id: string, extra: Partial<RegisteredSession> = {}): RegisteredSession {
  return {
    session_id, kind: "track", scale_px_per_m: 146.04, led_separation_m: 0.0686, rotation_rad: 0, flip: true, offset_m: [-0.7768, 1.6859], scale_x: 127.02, scale_y: 165.02,
    led_offset_rad: 3.07, led_offset_r: 0.0218, led_offset_n: 5280, warnings: [], built_at: "2026-10-18T17:48:26+00:00", ...extra,
  };
}

const cell = (key: string, row: RegisteredSession) => SORTABLE.find((c) => c.key === key)!.text(row);

test("the yaml parameters become facts, a list as its items and a nested group under its name", () => {
  const params = { corridor_width: 0.08, envelope: [1.6, 1.25], derived: { side_gap: 0.1, connector: 0.35 }, rotated_deg: 90 };
  expect(paramFacts(params)).toEqual([
    { label: "corridor_width", value: "0.08" },
    { label: "envelope", value: "1.6, 1.25" },
    { label: "derived side_gap", value: "0.1" },
    { label: "derived connector", value: "0.35" },
    { label: "rotated_deg", value: "90" },
  ]);
});

test("a row shows its scale with the two axis estimates on a track only, the angles in degrees, the LED separation in centimetres and the LED offset with its concentration and n", () => {
  const track = registration("A", { rotation_rad: -2.351 });
  const arena = registration("A", { kind: "arena", scale_x: undefined, scale_y: undefined });
  expect(cell("scale", track)).toBe("146.0 (x 127.0, y 165.0)");
  expect(cell("scale", arena)).toBe("146.0");
  expect(cell("rotation", track)).toBe("-134.7");
  expect(cell("led", track)).toBe("6.9");
  expect(cell("offset", track)).toBe("175.9, r 0.02, n 5280");
  expect(COLUMNS.map((c) => c.key)).toEqual(["session", "kind", "scale", "rotation", "led", "offset", "built"]);
});

test("the warnings are a count in the table's chip, each text on its own line in the row's title and in the expanded row's list, and the table sorts on the count", () => {
  const clean = registration("A");
  const warned = registration("B", { warnings: ["B track scale x and y differ", "B other"] });
  expect([clean, warned].map(WARNINGS.text)).toEqual(["0", "2"]);
  expect(rowTitle(warned)).toBe("B, track\nB track scale x and y differ\nB other");
  expect(sortRows([clean, warned], SORTABLE, { key: "warnings", descending: true }).map((r) => r.session_id)).toEqual(["B", "A"]);
  expect(registrationFacts(clean).slice(0, 2)).toEqual([{ label: "frame flip", value: "yes" }, { label: "frame offset", value: "-0.777, 1.686 m" }]);
});

test("the shortest arc of angles runs from its start to its end and goes past 180 when it crosses it, a hair under zero is not written -0", () => {
  const across = circularRange([-134.7, -0.04]);
  expect([across.from, across.to]).toEqual([expect.closeTo(-134.7), expect.closeTo(-0.04)]);
  expect(circularRange([170, -170])).toEqual({ from: 170, to: 190 });
  expect(circularRange([10, 20, 350])).toEqual({ from: -10, to: 20 });
  expect(circularRange([42])).toEqual({ from: 42, to: 42 });
  const line = rangesLine([registration("A", { rotation_rad: -0.0004 * RAD }), registration("B")], { n_sessions: 2, n_warned: 0 });
  expect(line).toContain("rotation 0.0 deg");
});

test("the ranges line gives the sessions, the ranges of scale, rotation and LED separation and the sessions with a warning, and nothing for an environment without sessions", () => {
  const rows = [
    registration("A", { scale_px_per_m: 145.9, rotation_rad: 170 * RAD, led_separation_m: 0.068 }),
    registration("B", { scale_px_per_m: 146.04, rotation_rad: -170 * RAD, led_separation_m: 0.0692, warnings: ["x"] }),
  ];
  expect(rangesLine(rows, { n_sessions: 2, n_warned: 1 })).toBe("2 sessions, scale 145.9 to 146.0 px per m, rotation 170.0 to 190.0 deg, LED separation 6.8 to 6.9 cm, 1 session with a warning");
  expect(rangesLine([rows[0]], { n_sessions: 1, n_warned: 0 })).toBe("1 session, scale 145.9 px per m, rotation 170.0 deg, LED separation 6.8 cm, 0 sessions with a warning");
  expect(rangesLine([], { n_sessions: 0, n_warned: 0 })).toBe("");
});

test("the shared extent holds every geometry so they are drawn at one scale", () => {
  const geometry = (corner: [number, number]) => ({ walls: [[[0, 0], corner]], boundary: null, centerline: [], reward_sites: {}, circle: null }) as unknown as Geometry;
  expect(sharedExtent([geometry([1, 2]), geometry([3, 1])])).toEqual({ x: [0, 3], y: [0, 2] });
});
