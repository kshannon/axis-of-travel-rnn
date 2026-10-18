import Alpine from "alpinejs";
import { errorText, getHealth } from "../api/client";
import type { Health, Kind } from "../api/types";
import { BlockPlayer } from "../session/block";
import { Workspace } from "../session/workspace";
import { toast } from "../ui/toast";
import { problemWith } from "./problem";

const SESSION_KEY = "ratreplay-session";

export interface HealthStore {
  found: Health | null;
  sessionId: string;
  load(reload?: boolean): Promise<boolean>;
  openSession(sessionId: string): void;
  problem(...kinds: Kind[]): string;
}

const foldersOf = (health: Health) => [health.transformed.root, health.processed.root].join("\n");

/** Register the health store: the folders the config names, read at boot, and the session open in the replay, which survives a reload. */
export function registerHealth(): void {
  const store: HealthStore = {
    found: null,
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
        return true;
      } catch (error) {
        toast.error(errorText(error));
        return false;
      }
    },
    openSession(sessionId: string) {
      this.sessionId = sessionId;
      localStorage.setItem(SESSION_KEY, sessionId);
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
