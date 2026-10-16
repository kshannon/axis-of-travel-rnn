// The shapes the API answers with, as ratreplay/backend/README.md lists them.

export type SourceKind = "transformed" | "processed";
export type Span = [first: number, last: number];

export interface ManifestInfo {
  timestamp: string;
  modified: string;
}

export interface Counts {
  sessions?: number;
  epochs?: number;
  runs?: number;
  frames?: number;
  blocks?: number;
  reviews?: number;
}

export interface Source {
  id: string;
  kind: SourceKind;
  path: string;
  processed_path: string;
  attached_at: string;
  status: "ok" | "invalid";
  problems: string[];
  counts: Counts;
  manifests: { transformed: ManifestInfo | null; processed: ManifestInfo | null };
}

export interface AttachBody {
  path: string;
  kind: SourceKind;
  processed_path?: string;
}

export interface Epoch {
  epoch: string;
  environment: string;
  condition: string;
  frame_start: number;
  frame_end: number;
  duration_s: number;
}

export interface Run {
  run: number;
  epoch: string | null;
  path_id: number;
  clean: boolean;
  frame_start: number;
  frame_end: number;
}

export interface AutomaticBlock {
  block_id: string;
  session_id: string;
  epoch: string;
  environment: string;
  frame_start: number;
  frame_end: number;
  n_frames: number;
  duration_s: number;
}

export interface SessionRow {
  session_id: string;
  subject_id: string;
  group: string;
  date: string;
  protocol: string;
  rate_hz: number;
  max_gap: number;
  epochs: Epoch[];
  n_runs: number;
  n_clean_runs: number;
  in_dataset: boolean;
  n_automatic: number | null;
  reviewed: boolean;
  reviewed_at: string | null;
  reviewed_by: string | null;
  n_confirmed: number;
  confirmed_s: Record<string, number>;
  notes: string;
}

export interface SessionHeader {
  session_id: string;
  subject_id: string;
  date: string;
  protocol: string;
  group: string;
  rate_hz: number;
  max_gap: number;
  n_frames: number;
  epochs: Epoch[];
  /** The epoch kinds the processor cuts into blocks. */
  block_epochs: string[];
  runs: Run[];
  cuts: { pauses: number[]; jumps: number[]; gaps: Span[]; margins: Span[] };
  heading_lost: Span[];
  heading_filled: Span[];
  heading_held: Span[];
  led_offset: { rad: number; r: number };
  occupancy: { bins: number; x: [number, number]; y: [number, number]; counts: Record<string, number[]> };
  blocks: AutomaticBlock[];
}

// One typed array per column of the Arrow streams, one row per frame.
export interface SessionArrays {
  t: Float64Array;
  x: Float64Array;
  y: Float64Array;
  heading: Float64Array;
  speed: Float64Array;
  motion: Float64Array;
  n_lights: Int8Array;
}

export interface BlockArrays {
  frame: Int32Array;
  t: Float64Array;
  x: Float64Array;
  y: Float64Array;
  heading: Float64Array;
  speed: Float64Array;
  n_lights: Int8Array;
}

export interface ReviewBlock {
  block_id: string;
  epoch: string;
  environment: string;
  frame_start: number;
  frame_end: number;
  status: "auto" | "confirmed" | "edited" | "dropped";
  note: string;
}

export type Edit =
  | { op: "accept" }
  | { op: "confirm"; frame: number }
  | { op: "move"; frame: number; edge: "start" | "end"; at: number }
  | { op: "split"; frame: number }
  | { op: "drop"; frame: number }
  | { op: "new"; frame_start: number; frame_end: number }
  | { op: "cut"; frame_start: number; frame_end: number }
  | { op: "flag"; run: number };

export interface Review {
  session_id: string;
  reviewed_by: string;
  reviewed_at: string;
  converter_manifest_timestamp: string;
  rules: Record<string, number | string>;
  blocks: ReviewBlock[];
  cuts: { frame_start: number; frame_end: number; reason: string }[];
  flagged_runs: number[];
  notes: string;
  edits: Edit[];
}

export interface ReviewBody {
  edits: Edit[];
  notes: string;
}

export interface SavedReview {
  review: Review;
  path: string;
  overwrote: boolean;
}

export interface ReviewPreview {
  blocks: ReviewBlock[];
  cuts: Review["cuts"];
  flagged_runs: number[];
  skipped: (Edit & { reason: string })[];
}

export interface WindowSettings {
  window_s: number;
  stride_s: number;
  burn_in_s: number;
  horizon_s: number;
  train_rate_hz: number;
  min_heading_measured: number;
  min_complete_trips: number;
}

export interface Totals {
  blocks_ok: number;
  blocks_trouble: number;
  windows: number;
  hours_ok: number;
}

export interface BlockRow {
  block_id: string;
  session_id: string;
  subject_id: string;
  date: string;
  protocol: string;
  environment: string;
  epoch: string;
  kind: string;
  status: string;
  reviewed_by: string | null;
  frame_start: number;
  frame_end: number;
  n_frames: number;
  duration_s: number;
  n_runs: number;
  n_clean_runs: number;
  n_trips: number;
  n_complete_trips: number;
  heading_lost_s: number;
  heading_filled_s: number;
  heading_held_s: number;
  heading_measured: number;
  n_windows: number;
  ok: boolean;
  reason: string;
}

export interface BlockIndex {
  blocks: BlockRow[];
  totals: Record<string, Totals>;
  settings: WindowSettings;
}

export interface Geometry {
  name: string;
  kind: string;
  room: [number, number];
  boundary: [number, number][] | null;
  walls: [number, number][][];
  centerline: { name: string; p0: [number, number]; p1: [number, number]; axis_deg: number }[];
  reward_sites: Record<string, [number, number]>;
  circle: { center: [number, number]; radius: number } | null;
}

export interface BlockWindow {
  index: number;
  first: number;
  burn_in_stop: number;
  window_stop: number;
  stop: number;
  position_finite: boolean;
  heading_measured: number;
  trips_complete: number;
  trips_partial: number;
  ok: boolean;
}

export interface BlockHeader {
  block_id: string;
  session_id: string;
  kind: string;
  status: string;
  environment: string;
  geometry: Geometry;
  n_frames: number;
  duration_s: number;
  rate_hz: number;
  frame_start: number;
  runs: { run: number; path_id: number; clean: boolean; first: number; last: number }[];
  trips: { trip: number; partial: boolean; first: number; last: number }[];
  phases: { phase: string; first: number; last: number }[];
  heading_filled: Span[];
  heading_held: Span[];
  one_light: Span[];
  verdict: { ok: boolean; reason: string };
  settings: WindowSettings;
  windows: BlockWindow[];
}

export interface SettingsAnswer {
  settings: WindowSettings;
  saved: {
    settings: WindowSettings;
    processed_manifest_timestamp: string;
    rules: Record<string, number | string>;
    totals: Record<string, Totals>;
    written_at: string;
  } | null;
  path: string;
}

export interface FormatColumn {
  name: string;
  type: string;
  required: boolean;
}

export interface FormatFile {
  path: string;
  optional: boolean;
  columns?: FormatColumn[];
  keys?: string[];
}

export interface FormatContract {
  version: number;
  transformed: { files: FormatFile[] };
  processed: { kinds: string[]; files: FormatFile[] };
  review: {
    path: string;
    keys: string[];
    block_keys: string[];
    statuses: string[];
    edits: Record<string, string[]>;
  };
  window_settings: WindowSettings;
}

// The parts of FastAPI's OpenAPI document the API page reads.
export interface SchemaNode {
  $ref?: string;
  type?: string;
  enum?: unknown[];
  items?: SchemaNode;
  anyOf?: SchemaNode[];
  oneOf?: SchemaNode[];
  properties?: Record<string, SchemaNode>;
  required?: string[];
  default?: unknown;
  description?: string;
}

export interface OpenApiParameter {
  name: string;
  in: string;
  required?: boolean;
  schema: SchemaNode;
  description?: string;
}

export interface OpenApiOperation {
  summary?: string;
  description?: string;
  parameters?: OpenApiParameter[];
  requestBody?: { required?: boolean; content: Record<string, { schema: SchemaNode }> };
  responses: Record<string, { description: string; content?: Record<string, { schema: SchemaNode }> }>;
}

export interface OpenApiDocument {
  info: { title: string; version: string };
  paths: Record<string, Record<string, OpenApiOperation>>;
  components?: { schemas?: Record<string, SchemaNode> };
}
