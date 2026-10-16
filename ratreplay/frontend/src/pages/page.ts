export interface Page {
  id: string;
  title: string;
  html: string;
  /** Registers the page's Alpine component, for pages that have one. */
  register?: () => void;
}
