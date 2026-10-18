import Alpine from "alpinejs";
import { ApiError, errorText, getFormat, getHealth, STALE_API, staleApi } from "../api/client";
import type { Health, Kind } from "../api/types";
import { BlockPlayer } from "../session/block";
import { Workspace } from "../session/workspace";
import { toast } from "../ui/toast";
import { problemWith } from "./problem";

const SESSION_KEY = "ratreplay-session";

export interface HealthStore {
  found: Health | null;
  /** The API's format has been checked against the page's. */
  checked: boolean;
  sessionId: string;
  load(reload?: boolean): Promise<boolean>;
  /** Whether the API is the one this page was built for, checked on the first load, a warning when it is not. */
  checkApi(): Promise<void>;
  openSession(sessionId: string): void;
  /** Let go of the open session for this visit, so the Replay shows its empty state. The one remembered for a reload stays, a failed read may only be the API being down. */
  closeSession(): void;
  problem(...kinds: Kind[]): string;
}

/** Say that the API is older than the page, once while the warning is on the stack. */
export const warnStale = (): void => toast.warningOnce(STALE_API);

const foldersOf = (health: Health) => [health.transformed.root, health.processed.root].join("\n");

/** Register the health store: the folders the config names, read at boot, and the session open in the replay, which survives a reload. */
export function registerHealth(): void {
  const store: HealthStore = {
    found: null,
    checked: false,
    sessionId: localStorage.getItem(SESSION_KEY) ?? "",
    /** Read the folders and say so when that fails. Another folder than before drops the work open on the old one. */
    async load(reload = false) {
      try {
        const next = await getHealth(reload);
        if (this.found && foldersOf(next) !== foldersOf(this.found)) {
          Workspace.current = null;
          BlockPlayer.current = null;
          this.openSession("");
        }
        this.found = next;
        if (!this.checked) {
          this.checked = true;
          void this.checkApi();
        }
        return true;
      } catch (error) {
        toast.error(errorText(error));
        return false;
      }
    },
    async checkApi() {
      try {
        if (staleApi(await getFormat())) warnStale();
      } catch (error) {
        // An API from before there was a format route answers 404.
        if (error instanceof ApiError && error.status === 404) warnStale();
        else toast.error(errorText(error));
      }
    },
    openSession(sessionId: string) {
      this.sessionId = sessionId;
      localStorage.setItem(SESSION_KEY, sessionId);
    },
    closeSession() {
      this.sessionId = "";
    },
    problem(...kinds: Kind[]) {
      return problemWith(this.found, kinds);
    },
  };
  Alpine.store("health", store);
}

export function healthStore(): HealthStore {
  return Alpine.store("health") as HealthStore;
}
