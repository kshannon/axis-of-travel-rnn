/** The page a location hash names, the first page when it names none. */
export function pageFromHash(hash: string, pageIds: readonly string[]): string {
  const id = hash.replace(/^#\/?/, "");
  return pageIds.includes(id) ? id : pageIds[0];
}

/**
 * One visit to a page, from the moment the shell mounts it to the moment it tears it down. The shell mounts only the page whose tab is
 * shown, so a page loads its data in `init` and not before. A load can still end after the person left, and what it says would land on
 * whatever page is shown by then, so the page asks its visit before it speaks.
 */
export class Visit {
  private on = true;

  get shown(): boolean {
    return this.on;
  }

  /** The person left the page: call it from the page's `destroy`. */
  hide(): void {
    this.on = false;
  }

  /** Try again every `everyMs` for `forMs` while the page is shown, until the attempt answers true. Gives back whether it did, and false when the page was left first. */
  async retry(attempt: () => Promise<boolean>, everyMs: number, forMs: number): Promise<boolean> {
    for (let waited = 0; waited < forMs; waited += everyMs) {
      await new Promise((resolve) => setTimeout(resolve, everyMs));
      if (!this.on) return false;
      if (await attempt()) return this.on;
    }
    return false;
  }

  /** Say something about the page's own work, such as a failure for the toast stack, only while the page is shown. */
  say(message: () => void): void {
    if (this.on) message();
  }
}
