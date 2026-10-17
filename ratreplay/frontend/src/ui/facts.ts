export interface Fact {
  label: string;
  value: string;
}

/** A list of label and value pairs, `facts` being the Alpine expression of the array. */
export function factsList(facts: string): string {
  return `
    <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
      <template x-for="fact in ${facts}" :key="fact.label">
        <div class="contents"><dt class="text-muted" x-text="fact.label"></dt><dd x-text="fact.value"></dd></div>
      </template>
    </dl>`;
}
