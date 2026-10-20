export type Theme = "dark" | "light";

const STORAGE_KEY = "ratreplay-theme";
const DEFAULT_THEME: Theme = "dark";

function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** Apply the stored theme, dark when none is stored. */
export function initTheme(): void {
  applyTheme(localStorage.getItem(STORAGE_KEY) === "light" ? "light" : DEFAULT_THEME);
}

/** Switch between dark and light and remember the choice. */
export function toggleTheme(): Theme {
  const next = currentTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  localStorage.setItem(STORAGE_KEY, next);
  return next;
}
