/** A coloured dot with its plain word, `status` being an Alpine expression that gives "ok" or "problem". */
export function statusMark(status: string): string {
  return `
    <span class="inline-flex shrink-0 items-center gap-1.5 text-xs" :class="${status} === 'ok' ? 'text-ok' : 'text-bad'">
      <span class="size-2.5 rounded-full" :class="${status} === 'ok' ? 'bg-ok' : 'bg-bad'"></span>
      <span x-text="${status}"></span>
    </span>`;
}
