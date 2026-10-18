export type ToastKind = "success" | "warning" | "error";

export interface Toast {
  id: number;
  kind: ToastKind;
  text: string;
  /** The file a save wrote, shown apart from the text so it can wrap anywhere. */
  path: string;
  /** The time of day it happened, hours to seconds. */
  time: string;
  leaving: boolean;
}

const LIFETIME_MS = 5000;
const FADE_MS = 500;
const MAX_TOASTS = 4;

const timeOfDay = (date: Date) => date.toLocaleTimeString("sv-SE");

/**
 * The toasts on screen, two behaviours in one queue. A success is brief: it fades for FADE_MS at the end of its LIFETIME_MS and only the
 * newest MAX_TOASTS stay. A warning or an error is held, newest first, until the person closes it.
 */
export class ToastQueue {
  /** The successes, oldest first. */
  items: Toast[] = [];
  /** The warnings and errors, newest first. */
  problems: Toast[] = [];
  nextId = 1;

  push(kind: ToastKind, text: string, path = ""): void {
    const id = this.nextId++;
    const toast = { id, kind, text, path, time: timeOfDay(new Date()), leaving: false };
    if (kind !== "success") {
      this.problems = [toast, ...this.problems];
      return;
    }
    this.items = [...this.items, toast].slice(-MAX_TOASTS);
    setTimeout(() => this.fade(id), LIFETIME_MS - FADE_MS);
  }

  fade(id: number): void {
    const toast = this.items.find((item) => item.id === id);
    if (!toast) return;
    toast.leaving = true;
    setTimeout(() => this.dismiss(id), FADE_MS);
  }

  dismiss(id: number): void {
    this.items = this.items.filter((item) => item.id !== id);
    this.problems = this.problems.filter((item) => item.id !== id);
  }
}
