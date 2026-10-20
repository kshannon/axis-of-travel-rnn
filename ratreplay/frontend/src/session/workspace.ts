import { getSession, getSessionArrays, previewEdits, saveBlocks, setExclusion } from "../api/client";
import type { Edit, ExclusionSaved, Preview, Review, SavedBlocks, SessionArrays, SessionHeader, WindowSettings } from "../api/types";
import { Clock } from "./clock";
import { Editor, NOTHING_CHANGED } from "./editor";
import { speedTop } from "./speed";

/** The start offset the field takes in metres, either way from none, and the step of its arrows. */
export const START_OFFSET_LIMIT = 0.5;
export const START_OFFSET_STEP = 0.01;

const sameResult = (a: Preview, b: Preview) =>
  JSON.stringify([a.blocks, a.flagged_runs, a.cuts]) === JSON.stringify([b.blocks, b.flagged_runs, b.cuts]);

/** The arrays as the views take them: each float32 column the API sends widened to float64, every other column as it came. */
export function widened(sent: object): SessionArrays {
  return Object.fromEntries(Object.entries(sent).map(([name, values]) => [name, values instanceof Float32Array ? Float64Array.from(values) : values])) as unknown as SessionArrays;
}

const arraysOf = async (...asked: Parameters<typeof getSessionArrays>) => widened(await getSessionArrays(...asked));

export interface Loaded {
  header: SessionHeader;
  arrays: SessionArrays;
  settings: WindowSettings;
  saved: Review | null;
  preview: Preview;
}

/**
 * The session under review: its arrays and playback clock as plain objects, and the edits with the blocks the server
 * makes of them. The browser never applies an edit, every change is the server's preview of the new edit list.
 */
export class Workspace {
  /** Kept while the person visits other pages, so edits not yet saved are still there on return. */
  static current: Workspace | null = null;

  header: SessionHeader;
  arrays: SessionArrays;
  settings: WindowSettings;
  readonly clock: Clock;
  readonly editor: Editor;
  speedTop: number;
  saved: Review | null;
  /** The start offset in metres the session is registered with, none for the yaml's. The header and the arrays are those of this offset. */
  startOffset: number | null;
  /** The start offset the review on disk holds. */
  private savedOffset: number | null;
  /** The person excluded the session. */
  excluded: boolean;
  preview: Preview;
  private queue: Promise<unknown> = Promise.resolve();

  constructor(loaded: Loaded) {
    this.header = loaded.header;
    this.arrays = loaded.arrays;
    this.settings = loaded.settings;
    this.saved = loaded.saved;
    this.excluded = loaded.header.excluded;
    this.preview = loaded.preview;
    this.clock = new Clock(loaded.header.n_frames, loaded.header.rate_hz);
    this.editor = new Editor(loaded.saved?.edits ?? []);
    this.speedTop = speedTop(loaded.arrays.speed);
    this.startOffset = this.savedOffset = loaded.header.start_offset_m;
  }

  /** Whether anything would be lost by leaving the session: edits not saved, or a start offset other than the saved one. */
  get dirty(): boolean {
    return this.editor.dirty || this.offsetDirty;
  }

  /** Whether the start offset differs from the one saved. */
  get offsetDirty(): boolean {
    return this.startOffset !== this.savedOffset;
  }

  /** The session loaded with its saved review at the settings, or the one already open with its blocks counted at the settings. */
  static async open(sessionId: string, settings: WindowSettings): Promise<Workspace> {
    const kept = Workspace.current;
    if (kept?.holds(sessionId)) {
      await kept.useSettings(settings);
      return kept;
    }
    const [header, arrays] = await Promise.all([getSession(sessionId, settings), arraysOf(sessionId)]);
    const { review: saved, blocks, refusals, cuts, flagged_runs } = header;
    return (Workspace.current = new Workspace({ header, arrays, settings, saved, preview: { blocks, refusals, cuts, flagged_runs } }));
  }

  /** Exclude a session or include it again: through the open workspace when it holds the session, so its saved review and flag follow, else straight to the API. */
  static exclude(sessionId: string, excluded: boolean, note: string, settings: WindowSettings): Promise<ExclusionSaved> {
    const kept = Workspace.current;
    return kept?.holds(sessionId) ? kept.setExclusion(excluded, note) : setExclusion(sessionId, excluded, note, settings);
  }

  /** The open session when opening this one would throw away its unsaved edits or start offset, none when they are saved or it is the one asked for. */
  static unsavedWhenOpening(sessionId: string): Workspace | null {
    const kept = Workspace.current;
    return kept?.dirty && !kept.holds(sessionId) ? kept : null;
  }

  private holds(sessionId: string): boolean {
    return this.header.session_id === sessionId;
  }

  /** Run a change after the ones before it, so two previews never cross. */
  private serially<T>(job: () => Promise<T>): Promise<T> {
    const next = this.queue.then(job, job);
    this.queue = next.catch(() => undefined);
    return next;
  }

  private previewOf(edits: Edit[], settings = this.settings, startOffset = this.startOffset): Promise<Preview> {
    return previewEdits(this.header.session_id, { edits, settings, start_offset_m: startOffset });
  }

  /** Count the blocks' windows at other settings: the whole edit list is previewed again, and the settings change only if that works. */
  useSettings(settings: WindowSettings): Promise<void> {
    return this.serially(async () => {
      if (JSON.stringify(settings) === JSON.stringify(this.settings)) return;
      this.preview = await this.previewOf(this.editor.edits, settings);
      this.settings = settings;
    });
  }

  /**
   * Register the session with another start offset, none for the yaml's: the header and the arrays are read again with it and the whole edit list is previewed under it.
   * The edits and the clock stay. Nothing changes if any of the three fails. When the offset is none the yaml's own number is asked for, so the offset of a saved review cannot stand in for it.
   * Gives back whether the session moved, which it does not when it already has that offset.
   */
  useStartOffset(offset: number | null): Promise<boolean> {
    return this.serially(async () => {
      if (offset === this.startOffset) return false;
      const { session_id: id } = this.header;
      const asked = offset ?? this.header.start_offset_default_m;
      const [header, arrays, preview] = await Promise.all([getSession(id, this.settings, asked), arraysOf(id, asked), this.previewOf(this.editor.edits, this.settings, offset)]);
      this.header = header;
      this.arrays = arrays;
      this.preview = preview;
      this.speedTop = speedTop(arrays.speed);
      this.startOffset = offset;
      return true;
    });
  }

  /** Add the edit made when the server applies it and it changes something. Gives back the edit added, or the reason it was not: the server's, or the words `unchanged` gives when the edit changes nothing. */
  edit(make: () => Edit | string, unchanged: () => string = () => NOTHING_CHANGED): Promise<Edit | string> {
    return this.serially(async () => {
      const edit = make();
      if (typeof edit === "string") return edit;
      const next = await this.previewOf([...this.editor.edits, edit]);
      if (next.refusals.length > this.preview.refusals.length) return next.refusals[next.refusals.length - 1].reason;
      if (sameResult(this.preview, next)) return unchanged();
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

  /** Exclude the session or include it again: the review on disk is rewritten with the flag and the note (or removed, when it only recorded the exclusion), the edits not saved stay. */
  setExclusion(excluded: boolean, note: string): Promise<ExclusionSaved> {
    return this.serially(async () => {
      const done = await setExclusion(this.header.session_id, excluded, note, this.settings);
      this.saved = done.review;
      this.excluded = done.review?.excluded ?? false;
      return done;
    });
  }

  /** Write the review whole, replacing the earlier one. */
  save(notes: string): Promise<SavedBlocks> {
    return this.serially(async () => {
      const saved = await saveBlocks(this.header.session_id, { edits: this.editor.edits, notes, settings: this.settings, start_offset_m: this.startOffset });
      this.saved = saved.review;
      this.editor.markSaved();
      this.savedOffset = this.header.start_offset_m = this.startOffset;
      return saved;
    });
  }
}
