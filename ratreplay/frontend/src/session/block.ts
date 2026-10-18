import { getBlock, getBlockArrays, getBlockWindows } from "../api/client";
import type { BlockArrays, BlockHeader, BlockWindows, WindowSettings } from "../api/types";
import { Clock } from "./clock";
import { speedTop } from "./speed";

/** The block under study: the header and arrays of a built block, its window rows and verdict at the settings, and its playback clock. */
export class BlockPlayer {
  /** Kept while the person visits other pages, so the Windows page finds the block the Blocks page opened. */
  static current: BlockPlayer | null = null;

  readonly clock: Clock;
  readonly speedTop: number;

  constructor(readonly header: BlockHeader, readonly arrays: BlockArrays, public windows: BlockWindows, public settings: WindowSettings) {
    this.clock = new Clock(header.row.n_frames, header.rate_hz);
    this.speedTop = speedTop(arrays.speed);
  }

  /** The block at the settings. Only the windows depend on them, so a block already open keeps its header, arrays and playback position. */
  static async open(blockId: string, settings: WindowSettings): Promise<BlockPlayer> {
    const kept = BlockPlayer.holding(blockId);
    if (kept) {
      await kept.useSettings(settings);
      return kept;
    }
    const [header, arrays, windows] = await Promise.all([getBlock(blockId), getBlockArrays(blockId), getBlockWindows(blockId, settings)]);
    return (BlockPlayer.current = new BlockPlayer(header, arrays, windows, settings));
  }

  /** The block open now, when a block id is given only if it is that one. */
  static holding(blockId?: string): BlockPlayer | null {
    const kept = BlockPlayer.current;
    return kept && (blockId === undefined || kept.header.row.block_id === blockId) ? kept : null;
  }

  /** Ask the server for the block's windows at other settings, which change only if that works. */
  async useSettings(settings: WindowSettings): Promise<void> {
    if (JSON.stringify(settings) === JSON.stringify(this.settings)) return;
    this.windows = await getBlockWindows(this.header.row.block_id, settings);
    this.settings = settings;
  }
}
