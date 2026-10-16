import Alpine from "alpinejs";
import { pageFromHash } from "../router";
import { currentTheme, toggleTheme } from "../ui/theme";

/** Register the shell component: which page is showing and which theme. */
export function registerShell(pageIds: readonly string[]): void {
  Alpine.data("shell", () => ({
    page: pageFromHash(location.hash, pageIds),
    dark: currentTheme() === "dark",
    go() {
      this.page = pageFromHash(location.hash, pageIds);
    },
    toggle() {
      this.dark = toggleTheme() === "dark";
    },
  }));
}
