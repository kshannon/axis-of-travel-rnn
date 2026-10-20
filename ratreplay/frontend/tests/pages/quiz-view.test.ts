import { expect, test } from "vitest";
import type { PairArrays, PairHeader, Reveal, SetRow, Tally } from "../../src/api/types";
import { guessBlocked, kindChoices, newPairBlocked, revealLine, setChoices, sharedFrames, sideChip, sideIndex, speedScene, tallyLine, tallyRows } from "../../src/pages/quiz-view";

const set = (set_id: string, created_at: string, kinds: string[]): SetRow => ({
  set_id, created_at, created_by: "kyle", sources: ["A"], seed: 3, length_s: {}, n_blocks: kinds.length, kinds, n_guesses: 0, n_correct: 0,
});

const reveal = (correct: boolean, real_side: "left" | "right"): Reveal => ({
  correct, real_side, real_block: "A_track_01", synthetic_block: "syn_1_track_01", tally: { n: 1, correct: Number(correct), by: {} },
});

const header = (n_frames: number, rate_hz = 60): PairHeader => ({ row: { kind: "track", environment: "t", n_frames, duration_s: n_frames / rate_hz, rate_hz }, rate_hz, geometry: {} as PairHeader["geometry"] });

test("the sets are offered newest first with what they hold, and the kinds are any then the set's own", () => {
  const choices = setChoices([set("syn_a", "2026-10-19T10:00:00+00:00", ["track"]), set("syn_b", "2026-10-19T11:00:00+00:00", ["arena", "track"])]);
  expect(choices).toEqual([{ value: "syn_b", label: "syn_b (2 blocks, arena, track)" }, { value: "syn_a", label: "syn_a (1 block, track)" }]);
  expect(kindChoices(["arena", "track"])).toEqual([{ value: "", label: "any kind" }, { value: "arena", label: "arena" }, { value: "track", label: "track" }]);
});

test("the buttons follow the phase: no pair opens without a set or while one is read, no answer before a pair is open or after it is answered", () => {
  expect(newPairBlocked("", "empty")).toBe("there is no synthetic set to quiz on, generate one on Synthetic");
  expect(newPairBlocked("syn_a", "loading")).toBe("a pair is being read");
  expect(newPairBlocked("syn_a", "open")).toBe("");
  expect(newPairBlocked("syn_a", "answered")).toBe("");
  expect(guessBlocked("empty")).toBe("open a pair first");
  expect(guessBlocked("loading")).toBe("the pair is being read");
  expect(guessBlocked("open")).toBe("");
  expect(guessBlocked("answered")).toBe("answered, open a new pair");
});

test("the reveal chips name the real side and the other synthetic, none before the answer, and the line says right or wrong with the blocks", () => {
  expect([sideChip(null, "left"), sideChip(null, "right")]).toEqual(["", ""]);
  expect([sideChip(reveal(true, "left"), "left"), sideChip(reveal(true, "left"), "right")]).toEqual(["real", "synthetic"]);
  expect([sideChip(reveal(false, "right"), "left"), sideChip(reveal(false, "right"), "right")]).toEqual(["synthetic", "real"]);
  expect(revealLine(reveal(true, "left"))).toBe("Right, the left block is real (A_track_01) and the right one is synthetic (syn_1_track_01).");
  expect(revealLine(reveal(false, "right"))).toBe("Wrong, the right block is real (A_track_01) and the left one is synthetic (syn_1_track_01).");
});

test("the tally line counts the pairs, the right ones and the share, and the table has a row per person, most answered first", () => {
  expect(tallyLine({ n: 0, correct: 0, by: {} })).toBe("No pair answered yet.");
  const tally: Tally = { n: 12, correct: 7, by: { ann: { n: 4, correct: 3 }, kyle: { n: 8, correct: 4 } } };
  expect(tallyLine(tally)).toBe("12 pairs answered, 7 right, 58 percent.");
  expect(tallyLine({ n: 1, correct: 1, by: {} })).toBe("1 pair answered, 1 right, 100 percent.");
  expect(tallyRows(tally)).toEqual([{ by: "kyle", answered: "8", right: "4", share: "50%" }, { by: "ann", answered: "4", right: "3", share: "75%" }]);
});

test("one clock runs both sides over the longer block by time, a side at another rate at its own frames, the shorter one holding its last frame, and the lane under a map is the speed trace alone", () => {
  expect(sharedFrames([header(1200), header(900)], 60)).toBe(1200);
  expect(sharedFrames([header(1200), header(900, 30)], 60)).toBe(1800);
  expect(sideIndex(1000, 60, header(900))).toBe(899);
  expect(sideIndex(100, 60, header(900))).toBe(100);
  expect(sideIndex(100, 60, header(900, 30))).toBe(50);
  const speed = new Float64Array([0, 0.1, 0.2]);
  const scene = speedScene(header(3), { speed } as PairArrays, 0.5);
  expect(scene.lanes).toEqual([{ name: "frames", label: "speed", weight: 1 }]);
  expect(scene.bars).toEqual([]);
  expect(scene.frames).toEqual([{ kind: "trace", values: speed, top: 0.5, colour: "var(--speed)" }]);
  expect([scene.nFrames, scene.rateHz]).toEqual([3, 60]);
});
