import { expect, test } from "vitest";
import { disabledWhy, KBD, LAYER_TOGGLE, SEGMENT, SEGMENT_PRIMARY, SEGMENTS } from "../../src/ui/style";

test("a disabled button says why and an enabled one keeps its title, both as Alpine attributes", () => {
  expect(disabledWhy("!hasSelection", "select a block first", "Split the block")).toBe(
    `:disabled="!hasSelection" :title="!hasSelection ? 'select a block first' : 'Split the block'"`,
  );
  // an apostrophe or a quote in the words does not end the attribute or the string
  expect(disabledWhy("busy", "it's \"busy\"")).toBe(`:disabled="busy" :title="busy ? 'it\\'s &quot;busy&quot;' : ''"`);
});

test("every segment looks like a plain button, a disabled one is muted, and a layer toggle is a plain box in the line colour", () => {
  const bare = (classes: string) => classes.split(" ").filter((name) => !name.includes(":"));
  expect(bare(SEGMENT_PRIMARY)).not.toContain("bg-accent");
  expect(SEGMENT).toContain("enabled:hover:bg-ink/15");
  for (const classes of [SEGMENT, SEGMENT_PRIMARY]) expect(classes).toContain("disabled:text-ink/40");
  expect(SEGMENTS).toContain("border-ink/30");
  expect(SEGMENTS).toContain("divide-ink/30");
  expect(LAYER_TOGGLE).toContain("border-line");
  expect(LAYER_TOGGLE).not.toMatch(/rounded-full|accent|has-/);
});

test("a key cap is a small raised key with a border and a line under it, in monospace, and takes no accent or hover like a button", () => {
  for (const name of ["rounded", "border", "font-mono", "text-xs"]) expect(KBD.split(" ")).toContain(name);
  expect(KBD).toMatch(/shadow-\[0_1px_0_/);
  expect(KBD).not.toMatch(/accent|hover:/);
});
