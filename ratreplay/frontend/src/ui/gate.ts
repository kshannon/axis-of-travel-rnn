/** The body of a page that needs a source: a notice linking to the Data page until one of the right kind is selected. */
export function sourceGate(body: string, kind = ""): string {
  const problem = `$store.source.problem('${kind}')`;
  return `
    <div class="h-full">
      <template x-if="${problem}">
        <div class="flex flex-col items-start gap-2 text-sm">
          <p x-text="${problem}"></p>
          <a href="#/data" class="text-accent underline">Choose a source on the Data page</a>
        </div>
      </template>
      <template x-if="!${problem}">${body}</template>
    </div>`;
}
