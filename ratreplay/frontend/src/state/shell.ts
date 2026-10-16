import Alpine from "alpinejs";
import { pageFromHash } from "../router";
import { currentTheme, toggleTheme } from "../ui/theme";

interface ShellStore {
  page: string;
  dark: boolean;
  init(): void;
  toggle(): void;
}

/** Register the shell store: which page is showing, following the location hash, and which theme. */
export function registerShell(pageIds: readonly string[]): void {
  const store: ShellStore = {
    page: pageFromHash(location.hash, pageIds),
    dark: currentTheme() === "dark",
    init() {
      addEventListener("hashchange", () => (this.page = pageFromHash(location.hash, pageIds)));
    },
    toggle() {
      this.dark = toggleTheme() === "dark";
    },
  };
  Alpine.store("shell", store);
}
