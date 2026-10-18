import { getBlock, getBlockArrays, getBlockWindows } from "../api/client";
import type { BlockArrays, BlockHeader, BlockWindow, BlockWindows, Verdict, WindowSettings } from "../api/types";
import { Clock } from "./clock";
import { speedTop } from "./speed";

/**
 * The block as the Blocks and Windows pages read it until F3 reshapes them: the API's header with the facts of its row, its
 * window rows and verdict at the settings, and those settings, merged in. The block header carries no rate, it is the
 * block's frames over its seconds.
 */
export interface BlockView extends BlockHeader {
  block_id: string;
  session_id: string;
  kind: string;
  status: string;
  n_frames: number;
  duration_s: number;
  rate_hz: number;
  windows: BlockWindow[];
  verdict: Verdict;
  settings: WindowSettings;
}

function viewOf(header: BlockHeader, found: BlockWindows, settings: WindowSettings): BlockView {
  const { row } = header;
  return {
    ...header, block_id: row.block_id, session_id: row.session_id, kind: row.kind, status: row.status, n_frames: row.n_frames,
    duration_s: row.duration_s, rate_hz: Math.round(row.n_frames / row.duration_s), windows: found.rows, verdict: found.verdict, settings,
  };
}

/** The block under study: its header at the window settings, its arrays and its playback clock. */
export class BlockPlayer {
  /** Kept while the person visits other pages, so the Windows page finds the block the Blocks page opened. */
  static current: BlockPlayer | null = null;

  readonly clock: Clock;
  readonly speedTop: number;

  constructor(readonly header: BlockView, readonly arrays: BlockArrays, clock?: Clock) {
    this.clock = clock ?? new Clock(header.n_frames, header.rate_hz);
    this.speedTop = speedTop(arrays.speed);
  }

  /** The block at the settings. Only the windows depend on them, so the arrays and the playback position of the block already open are kept. */
  static async open(blockId: string, settings: WindowSettings): Promise<BlockPlayer> {
    const kept = BlockPlayer.holding(blockId);
    const [header, found, arrays] = await Promise.all([getBlock(blockId), getBlockWindows(blockId, settings), kept?.arrays ?? getBlockArrays(blockId)]);
    return (BlockPlayer.current = new BlockPlayer(viewOf(header, found, settings), arrays, kept?.clock));
  }

  /** The block open now, when a block id is given only if it is that one. */
  static holding(blockId?: string): BlockPlayer | null {
    const kept = BlockPlayer.current;
    return kept && (blockId === undefined || kept.header.block_id === blockId) ? kept : null;
  }
}
