/** A number with its noun, the noun made plural unless the number is one. */
export function counted(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}
