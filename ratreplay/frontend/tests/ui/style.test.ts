import { expect, test } from "vitest";
import { disabledWhy, LAYER_TOGGLE, SEGMENT, SEGMENT_PRIMARY, SEGMENTS } from "../../src/ui/style";

test("a disabled button says why and an enabled one keeps its title, both as Alpine attributes", () => {
  expect(disabledWhy("!hasSelection", "select a block first", "Split the block")).toBe(
    `:disabled="!hasSelection" :title="!hasSelection ? 'select a block first' : 'Split the block'"`,
  );
  // an apostrophe or a quote in the words does not end the attribute or the string
  expect(disabledWhy("busy", "it's \"busy\"")).toBe(`:disabled="busy" :title="busy ? 'it\\'s &quot;busy&quot;' : ''"`);
});

test("the primary segment takes the accent only while enabled, a disabled one is muted like the others, and a layer toggle is a plain box in the line colour", () => {
  const bare = (classes: string) => classes.split(" ").filter((name) => !name.includes(":"));
  expect(bare(SEGMENT_PRIMARY)).not.toContain("bg-accent");
  expect(SEGMENT).toContain("enabled:hover:bg-accent");
  for (const classes of [SEGMENT, SEGMENT_PRIMARY]) expect(classes).toContain("disabled:text-ink/40");
  expect(SEGMENTS).toContain("border-line");
  expect(SEGMENTS).toContain("divide-line");
  expect(LAYER_TOGGLE).toContain("border-line");
  expect(LAYER_TOGGLE).not.toMatch(/rounded-full|accent|has-/);
});
