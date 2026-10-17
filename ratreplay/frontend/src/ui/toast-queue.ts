export type ToastKind = "success" | "warning" | "error";

export interface Toast {
  id: number;
  kind: ToastKind;
  text: string;
  /** The file a save wrote, shown apart from the text so it can wrap anywhere. */
  path: string;
  leaving: boolean;
}

const LIFETIME_MS = 5000;
const FADE_MS = 500;
const MAX_TOASTS = 4;

/** The toasts on screen: each fades for FADE_MS at the end of its LIFETIME_MS, and only the newest MAX_TOASTS stay. */
export class ToastQueue {
  items: Toast[] = [];
  nextId = 1;

  push(kind: ToastKind, text: string, path = ""): void {
    const id = this.nextId++;
    this.items = [...this.items, { id, kind, text, path, leaving: false }].slice(-MAX_TOASTS);
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
  }
}
