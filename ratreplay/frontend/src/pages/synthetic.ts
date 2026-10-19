import Alpine from "alpinejs";
import { deleteSet, errorText, generateSet, getSet, listSessions, listSets } from "../api/client";
import type { SessionRow, SetHeader } from "../api/types";
import { Visit } from "../router";
import { healthStore } from "../state/health";
import { settingsStore } from "../state/settings";
import { folderPage } from "../ui/gate";
import { counted, settingsText } from "../ui/text";
import { toast } from "../ui/toast";
import type { Page } from "./page";
import { syntheticRoot } from "./synthetic-html";
import { compareCaption, compareTables, DEFAULT_MINUTES, deletePrompt, generateBlocked, generatedText, lengthsOf, randomSeed, setLines, sourceChoices } from "./synthetic-view";
import type { CompareTable, SetLine } from "./synthetic-view";

// The set chosen for the comparison, kept while the person visits other pages.
let chosenSet = "";

function registerSynthetic(): void {
  Alpine.data("syntheticPage", () => {
    const visit = new Visit();
    // Each read of a set is numbered so that only the latest answer counts.
    let latest = 0;

    return {
      lines: [] as SetLine[],
      sessions: [] as SessionRow[],
      loading: true,
      error: "",
      busy: false,
      generating: false,
      sources: [] as string[],
      seed: randomSeed(),
      minutes: { ...DEFAULT_MINUTES } as Record<string, number>,
      settingsLine: "",
      chosen: chosenSet,
      header: null as SetHeader | null,
      tables: [] as CompareTable[],
      caption: "",
      compareError: "",

      get blocked() {
        return generateBlocked(this.sources, this.seed, this.minutes);
      },

      /** The sets and the built sessions, the settings in use, and the set chosen on the last visit. */
      async init() {
        try {
          this.settingsLine = settingsText(await settingsStore().load());
          await this.refresh();
          if (this.chosen) await this.compare();
        } catch (error) {
          this.error = errorText(error);
        }
        this.loading = false;
      },
      destroy() {
        visit.hide();
      },

      /** The sets table and the sources to choose from, read together. */
      async refresh() {
        const [sets, sessions] = await Promise.all([listSets(), listSessions()]);
        this.lines = setLines(sets);
        this.sessions = sourceChoices(sessions);
        this.error = "";
      },

      /** Read the chosen set and lay its two recipes side by side. */
      async compare() {
        const mine = ++latest;
        this.header = null;
        this.compareError = "";
        try {
          const header = await getSet(this.chosen);
          if (mine !== latest) return;
          this.header = header;
          this.tables = compareTables(header.recipe_real, header.recipe_synthetic);
          this.caption = compareCaption(header.set_id, header.sources, header.seed);
        } catch (error) {
          if (mine === latest) this.compareError = errorText(error);
        }
      },

      choose(setId: string) {
        this.chosen = setId;
        chosenSet = setId;
        void this.compare();
      },

      /** Generate a set from the form, say what it made, and show it in the table and the comparison. */
      async generate() {
        this.busy = true;
        this.generating = true;
        try {
          const settings = await settingsStore().load();
          const result = await generateSet({ sources: [...this.sources], seed: this.seed, length_s: lengthsOf(this.minutes), settings });
          if (result.failed.length || result.warnings.length) toast.warning(generatedText(result));
          else toast.success(generatedText(result));
          await this.refresh();
          this.choose(result.set_id);
          await healthStore().load();
        } catch (error) {
          visit.say(() => toast.error(errorText(error)));
        } finally {
          this.busy = false;
          this.generating = false;
        }
      },

      /** Delete a set after a confirmation, its blocks and guesses with it. */
      async remove(setId: string) {
        if (!confirm(deletePrompt(setId))) return;
        this.busy = true;
        try {
          const gone = await deleteSet(setId);
          toast.success(`Deleted set ${setId}, ${counted(gone.blocks, "block")} with it`);
          if (this.chosen === setId) {
            this.chosen = "";
            chosenSet = "";
            this.header = null;
          }
          await this.refresh();
          await healthStore().load();
        } catch (error) {
          visit.say(() => toast.error(errorText(error)));
        } finally {
          this.busy = false;
        }
      },
    };
  });
}

export const syntheticPage: Page = {
  id: "synthetic",
  title: "Synthetic",
  html: folderPage("Synthetic", syntheticRoot, "processed", "synthetic", "environments"),
  register: registerSynthetic,
};
