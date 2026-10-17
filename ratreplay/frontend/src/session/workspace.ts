import { getReview, getSession, getSessionArrays, getWindowSettings, previewReview, putReview } from "../api/client";
import type { Edit, Review, ReviewPreview, SavedReview, SessionArrays, SessionHeader, WindowSettings } from "../api/types";
import { Clock } from "./clock";
import { Editor } from "./editor";
import { speedTop } from "./speed";

const NO_CHANGE = "That changes nothing.";

const sameResult = (a: ReviewPreview, b: ReviewPreview) =>
  JSON.stringify([a.blocks, a.flagged_runs, a.cuts]) === JSON.stringify([b.blocks, b.flagged_runs, b.cuts]);

export interface Loaded {
  sid: string;
  header: SessionHeader;
  arrays: SessionArrays;
  settings: WindowSettings;
  saved: Review | null;
  preview: ReviewPreview;
}

/**
 * The session under review: its arrays and playback clock as plain objects, and the edits with the blocks the server
 * makes of them. The browser never applies an edit, every change is the server's preview of the new edit list.
 */
export class Workspace {
  /** Kept while the person visits other pages, so edits not yet saved are still there on return. */
  static current: Workspace | null = null;

  readonly sid: string;
  readonly header: SessionHeader;
  readonly arrays: SessionArrays;
  settings: WindowSettings;
  readonly clock: Clock;
  readonly editor: Editor;
  readonly speedTop: number;
  saved: Review | null;
  preview: ReviewPreview;
  private queue: Promise<unknown> = Promise.resolve();

  constructor(loaded: Loaded) {
    this.sid = loaded.sid;
    this.header = loaded.header;
    this.arrays = loaded.arrays;
    this.settings = loaded.settings;
    this.saved = loaded.saved;
    this.preview = loaded.preview;
    this.clock = new Clock(loaded.header.n_frames, loaded.header.rate_hz);
    this.editor = new Editor(loaded.saved?.edits ?? []);
    this.speedTop = speedTop(loaded.arrays.speed);
  }

  /** The session of a source loaded with its saved review, or the one already open with the window settings read again. */
  static async open(sid: string, sessionId: string): Promise<Workspace> {
    const kept = Workspace.current;
    if (kept?.holds(sid, sessionId)) {
      kept.settings = (await getWindowSettings()).settings; // the Blocks page may have saved new ones
      return kept;
    }
    const [header, arrays, saved, { settings }] = await Promise.all([
      getSession(sid, sessionId), getSessionArrays(sid, sessionId), getReview(sid, sessionId), getWindowSettings(),
    ]);
    const preview = await previewReview(sid, sessionId, saved?.edits ?? []);
    return (Workspace.current = new Workspace({ sid, header, arrays, settings, saved, preview }));
  }

  /** The open session when opening this one would throw away its unsaved edits, none when they are saved or it is the one asked for. */
  static unsavedWhenOpening(sid: string, sessionId: string): Workspace | null {
    const kept = Workspace.current;
    return kept?.editor.dirty && !kept.holds(sid, sessionId) ? kept : null;
  }

  private holds(sid: string, sessionId: string): boolean {
    return this.sid === sid && this.header.session_id === sessionId;
  }

  /** Run a change after the ones before it, so two previews never cross. */
  private serially<T>(job: () => Promise<T>): Promise<T> {
    const next = this.queue.then(job, job);
    this.queue = next.catch(() => undefined);
    return next;
  }

  private previewOf(edits: Edit[]): Promise<ReviewPreview> {
    return previewReview(this.sid, this.header.session_id, edits);
  }

  /** Add the edit made when the server applies it and it changes something. Gives back the edit added, or the reason it was not. */
  edit(make: () => Edit | string): Promise<Edit | string> {
    return this.serially(async () => {
      const edit = make();
      if (typeof edit === "string") return edit;
      const next = await this.previewOf([...this.editor.edits, edit]);
      if (next.skipped.length > this.preview.skipped.length) return next.skipped[next.skipped.length - 1].reason;
      if (sameResult(this.preview, next)) return NO_CHANGE;
      this.editor.push(edit);
      this.preview = next;
      return edit;
    });
  }

  /** Take the last edit back, gives it back, none when there was nothing to undo. */
  undo(): Promise<Edit | undefined> {
    return this.serially(async () => {
      const last = this.editor.edits.at(-1);
      if (!last) return undefined;
      this.preview = await this.previewOf(this.editor.edits.slice(0, -1));
      this.editor.undo();
      return last;
    });
  }

  /** Drop every edit, so the blocks are the automatic ones. A saved review stays on disk until the next save. */
  reset(): Promise<void> {
    return this.serially(async () => {
      this.preview = await this.previewOf([]);
      this.editor.reset();
    });
  }

  /** Write the review whole, replacing the earlier one. */
  save(notes: string): Promise<SavedReview> {
    return this.serially(async () => {
      const saved = await putReview(this.sid, this.header.session_id, { edits: this.editor.edits, notes });
      this.saved = saved.review;
      this.editor.markSaved();
      return saved;
    });
  }
}
