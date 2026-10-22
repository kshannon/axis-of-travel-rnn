/** The keyboard essentials, everything else is a button or a chip. */
export const KEYS: readonly { keys: string; action: string }[] = [
  { keys: "space", action: "play and pause" },
  { keys: "left, right", action: "one frame back or forward" },
  { keys: "shift with left, right", action: "one second back or forward" },
  { keys: "[ and ]", action: "previous and next run" },
  { keys: "enter", action: "confirm the selected block" },
  { keys: "a", action: "accept the selected block" },
  { keys: "r", action: "reject the selected block, again to restore it" },
  { keys: "escape", action: "clear the marks, then the selection" },
  { keys: "z", action: "undo the last edit" },
];

export type Command = "play" | "back" | "forward" | "back-second" | "forward-second" | "previous-run" | "next-run" | "confirm" | "accept" | "reject" | "clear" | "undo";

const COMMANDS: Record<string, Command> = {
  " ": "play", ArrowLeft: "back", ArrowRight: "forward", "[": "previous-run", "]": "next-run", Enter: "confirm", a: "accept", r: "reject", Escape: "clear", z: "undo",
};
const SECOND_WITH_SHIFT: Partial<Record<Command, Command>> = { back: "back-second", forward: "forward-second" };
const TEXT_FIELDS = ["INPUT", "TEXTAREA", "SELECT"];
const ACTIVATES = [" ", "Enter"];

/** The command a key press stands for, none for a key the page does not use or one with a modifier a browser shortcut owns. */
export function commandOf(event: Pick<KeyboardEvent, "key" | "shiftKey" | "ctrlKey" | "metaKey" | "altKey">): Command | null {
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  const command = COMMANDS[event.key] ?? null;
  return (event.shiftKey && command && SECOND_WITH_SHIFT[command]) || command;
}

/** Whether the press belongs to the element focused: typing in a field, or space and enter on a button or a link. */
export function belongsToTarget(event: { key: string; target: { tagName: string } | null }): boolean {
  const tag = event.target?.tagName ?? "";
  return TEXT_FIELDS.includes(tag) || (["BUTTON", "A"].includes(tag) && ACTIVATES.includes(event.key));
}
