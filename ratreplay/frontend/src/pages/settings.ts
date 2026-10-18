import Alpine from "alpinejs";
import { errorText, getFormat, getSelected, listBlocks, selectSettings } from "../api/client";
import type { WindowSettings } from "../api/types";
import { healthStore } from "../state/health";
import { settingsStore } from "../state/settings";
import { toast } from "../ui/toast";
import type { Page } from "./page";
import { settingsRoot } from "./settings-html";
import { atDefaults, fieldRows, ruleRows, selectedLine, testedLine } from "./settings-view";
import type { FieldRow, RuleRow } from "./settings-view";

const NOTHING_BUILT = "Nothing is built yet, so there is nothing to select these settings for";

function registerSettings(): void {
  Alpine.data("settingsPage", () => {
    // Each change is numbered so that only the latest answer counts.
    let latest = 0;

    return {
      loading: true,
      busy: false,
      defaults: null as WindowSettings | null,
      draft: {} as WindowSettings,
      rules: [] as RuleRow[],
      triedLine: "",
      selectedLine: "",
      selectBlocked: NOTHING_BUILT,

      get fields(): FieldRow[] {
        return fieldRows(this.defaults);
      },
      get isDefault() {
        return atDefaults(this.draft, this.defaults);
      },
      get canSelect() {
        return !this.busy && !this.loading && (healthStore().found?.processed.counts.blocks ?? 0) > 0;
      },

      /** The fields at the settings in use, the defaults and the rules from the format, and the selection. */
      async init() {
        try {
          const [format, current, selected] = await Promise.all([getFormat(), settingsStore().load(), getSelected()]);
          this.defaults = format.settings;
          this.rules = ruleRows(format.rules);
          this.draft = { ...current };
          this.triedLine = testedLine(current);
          this.selectedLine = selectedLine(selected.selected);
        } catch (error) {
          toast.error(errorText(error));
        }
        this.loading = false;
      },

      /** The API checks the settings in the fields, and they become the settings in use, the other pages' too, once it accepts them. Gives back the settings it accepted, none when a newer change took over. */
      async judge(): Promise<WindowSettings | null> {
        const mine = ++latest;
        const index = await listBlocks({ ...this.draft });
        if (mine !== latest) return null;
        settingsStore().use(index.settings);
        this.triedLine = testedLine(index.settings);
        return { ...index.settings };
      },

      /** A field changed: check the settings and say so when the API refuses them. */
      async change() {
        this.busy = true;
        try {
          await this.judge();
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },

      async reset() {
        this.draft = { ...this.defaults! };
        await this.change();
      },

      /** Check the settings in the fields, then select exactly the settings accepted, whatever changes while that is awaited. */
      async select() {
        this.busy = true;
        try {
          const judged = await this.judge();
          if (!judged) {
            toast.warning("The settings changed while they were being checked, nothing was selected, try again.");
            return;
          }
          const saved = await selectSettings(judged);
          this.selectedLine = selectedLine((await getSelected()).selected);
          toast.success(`Selected these settings, ${saved.replaced ? "replacing the earlier selection" : "a new file"}`, saved.file);
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },
    };
  });
}

export const settingsPage: Page = {
  id: "settings",
  title: "Settings",
  html: settingsRoot,
  register: registerSettings,
};
