import Alpine from "alpinejs";
import { getFormat } from "../api/client";
import type { WindowSettings } from "../api/types";

export interface SettingsStore {
  /** The window settings in use, none until the API has been asked for its defaults. */
  current: WindowSettings | null;
  /** The settings in use, the API's defaults the first time. */
  load(): Promise<WindowSettings>;
  /** Use these settings from now on. Every page that shows window counts watches `current`. */
  use(next: WindowSettings): void;
}

/** Register the settings store: the one place the window settings being tried live, held in the client and sent with every call that needs them. */
export function registerSettings(): void {
  const store: SettingsStore = {
    current: null,
    async load() {
      if (!this.current) {
        const { settings } = await getFormat();
        this.current ??= settings; // a use() while the format was coming wins
      }
      return this.current!;
    },
    use(next: WindowSettings) {
      this.current = { ...next };
    },
  };
  Alpine.store("settings", store);
}

export function settingsStore(): SettingsStore {
  return Alpine.store("settings") as SettingsStore;
}
