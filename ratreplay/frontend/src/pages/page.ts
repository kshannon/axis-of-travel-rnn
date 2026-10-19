/** The shell mounts the html of the page whose tab is shown and removes it on leaving, so a page's component runs `init` when the page is shown and `destroy` when it is left. */
export interface Page {
  id: string;
  title: string;
  html: string;
  /** Registers the page's Alpine component, for pages that have one. */
  register?: () => void;
}
