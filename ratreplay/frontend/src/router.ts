/** The page a location hash names, the first page when it names none. */
export function pageFromHash(hash: string, pageIds: readonly string[]): string {
  const id = hash.replace(/^#\/?/, "");
  return pageIds.includes(id) ? id : pageIds[0];
}
