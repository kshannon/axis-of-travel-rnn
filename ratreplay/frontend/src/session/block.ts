import { getBlock, getBlockArrays } from "../api/client";
import type { BlockArrays, BlockHeader, WindowSettings } from "../api/types";
import { Clock } from "./clock";
import { speedTop } from "./speed";

/** The block under study: its header at the window settings, its arrays and its playback clock. */
export class BlockPlayer {
  /** Kept while the person visits other pages, so the Windows page finds the block the Blocks page opened. */
  static current: BlockPlayer | null = null;

  readonly clock: Clock;
  readonly speedTop: number;

  constructor(readonly header: BlockHeader, readonly arrays: BlockArrays, clock?: Clock) {
    this.clock = clock ?? new Clock(header.n_frames, header.rate_hz);
    this.speedTop = speedTop(arrays.speed);
  }

  /** The block at the settings. Only the header depends on them, so the arrays and the playback position of the block already open are kept. */
  static async open(blockId: string, settings: WindowSettings): Promise<BlockPlayer> {
    const kept = BlockPlayer.holding(blockId);
    const [header, arrays] = await Promise.all([getBlock(blockId, settings), kept?.arrays ?? getBlockArrays(blockId)]);
    return (BlockPlayer.current = new BlockPlayer(header, arrays, kept?.clock));
  }

  /** The block open now, when a block id is given only if it is that one. */
  static holding(blockId?: string): BlockPlayer | null {
    const kept = BlockPlayer.current;
    return kept && (blockId === undefined || kept.header.block_id === blockId) ? kept : null;
  }
}
