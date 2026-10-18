import { expect, test } from "vitest";
import { disabledWhy } from "../../src/ui/style";

test("a disabled button says why and an enabled one keeps its title, both as Alpine attributes", () => {
  expect(disabledWhy("!hasSelection", "select a block first", "Split the block")).toBe(
    `:disabled="!hasSelection" :title="!hasSelection ? 'select a block first' : 'Split the block'"`,
  );
  // an apostrophe or a quote in the words does not end the attribute or the string
  expect(disabledWhy("busy", "it's \"busy\"")).toBe(`:disabled="busy" :title="busy ? 'it\\'s &quot;busy&quot;' : ''"`);
});
