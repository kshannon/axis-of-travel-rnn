// The shapes the API answers with, read from ratreplay/backend/ratreplay_api (routers, managers, engines) and its integration tests.

export type Kind = "transformed" | "processed" | "synthetic" | "environments";
export type Span = [first: number, last: number];

/** A stretch of lost, filled or held head direction: its first and last lab frame, its length, and why the engine left it so. */
export interface HeadingSpan {
  first: number;
  last: number;
  seconds: number;
  reason: string;
}

/** The times a folder reports. The converter run's timestamp is the transformed folder's alone. */
export interface ManifestInfo {
  timestamp?: string;
  modified: string;
}

export interface Counts {
  sessions?: number;
  epochs?: number;
  runs?: number;
  frames?: number;
  reviews?: number;
  blocks?: number;
  environments?: number;
  sets?: number;
  guesses?: number;
}

/** One folder as its access reports it. The root is null when the config lacks the key, the counts are empty while it has problems. */
export interface Folder {
  root: string | null;
  exists: boolean;
  problems: string[];
  counts: Counts;
  manifest: ManifestInfo | null;
}

export interface Health {
  transformed: Folder;
  processed: Folder;
  synthetic: Folder;
  environments: Folder;
  config_path: string;
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

/** The window settings, every key the API knows and no other, since it refuses an unknown one. */
export interface WindowSettings {
  window_s: number;
  stride_s: number;
  burn_in_s: number;
  horizon_s: number;
  rate_hz: number;
  min_heading_measured: number;
  min_complete_trips: number;
}

/** Whether a block is fit for training and every rule it breaks. */
export interface Verdict {
  ok: boolean;
  reasons: string[];
}

/** One row of the sessions index. The review facts are empty for a session no one reviewed. */
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
  /** Why the tool cannot work with the session (no frames, no arena or track epoch under the condition), none when it can. */
  reason: string | null;
  /** The lab's annotations mark the session excluded. Shown as a note, never applied. */
  annotated_exclude: boolean;
  /** The person excluded the session, in its review. */
  excluded: boolean;
  /** Who set the flag and when, none until it was set. */
  excluded_by: string | null;
  excluded_at: string | null;
  /** The blocks built from the session on disk. */
  built: number;
  /** A person has looked at the session: it is excluded, or has edits, or a block no longer auto. */
  reviewed: boolean;
  reviewed_at: string | null;
  reviewed_by: string | null;
  n_confirmed: number;
  confirmed_s: Record<string, number>;
  notes: string;
}

/** What cut a session: an epoch start, a pause, a jump, or a gap that runs to frame_end. */
export interface CutPoint {
  frame: number;
  frame_end?: number;
  reason: "epoch" | "pause" | "jump" | "gap";
}

export interface Stretch {
  epoch: string;
  frame_start: number;
  frame_end: number;
}

/** Where the session spent its frames: a grid of bins by bins over the room in metres (x and y give its extent), the counts of each epoch kind row by row from the lowest y. */
export interface Occupancy {
  bins: number;
  x: [number, number];
  y: [number, number];
  counts: Record<string, number[]>;
  /** The positions that fell outside the room. */
  outside: number;
}

/** The registration of the session: the LED offset and the pixel scale of each epoch kind. */
export interface SessionFrame {
  led_offset_rad: number;
  led_offset_r: number;
  led_offset_n: number;
  start_px: [number, number];
  goals_px: [number, number];
  arena?: Registration;
  /** The track's registration, with the start offset measured from the session's own occupancy (a number or none, missing from a build made before it was recorded). Absent for a session with no track epoch. */
  track?: Registration & { start_offset_measured_m?: number | null };
}

export interface Registration {
  scale_px_per_m: number;
  led_separation_m: number;
  rotation_rad: number;
  rotation_concentration: number;
  flip: boolean;
  offset_m: [number, number];
}

export interface ReviewBlock {
  block_id: string;
  epoch: string;
  environment: string;
  frame_start: number;
  frame_end: number;
  status: "auto" | "confirmed" | "edited" | "dropped";
  /** None for a block no one has annotated, the old review files hold an empty text. */
  note: string | null;
}

/** A block the edits make, with its windows at the settings (none for a removed block) and the problems of its frames. */
export interface MadeBlock extends ReviewBlock {
  windows: { count: number; verdict: Verdict } | null;
  problems: string[];
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

/** An edit the rules refused, by its place in the list. */
export interface Refusal {
  index: number;
  op: string;
  reason: string;
}

export interface Cut {
  frame_start: number;
  frame_end: number;
  reason: string;
}

export interface Review {
  session_id: string;
  /** None for a review that only records an exclusion, which reviews nothing. */
  reviewed_by: string | null;
  reviewed_at: string | null;
  converter_manifest_timestamp: string;
  rules: Record<string, unknown>;
  blocks: ReviewBlock[];
  cuts: Cut[];
  flagged_runs: number[];
  notes: string;
  edits: Edit[];
  /** The person excluded the session. */
  excluded: boolean;
  /** Who set the flag and when, none until it was set. */
  excluded_by: string | null;
  excluded_at: string | null;
}

/** The rules the engine cut and filled the session under, the ones the timeline's layers explain. The header carries all of them, these are the ones the page reads. */
export interface SessionRules {
  /** A step in time over this many seconds is a pause. */
  pause_step_s: number;
  /** Whether a tracking gap needs "both" lights unfilled or "either". */
  gap_lights: string;
  /** A step in position over this many pixels is a jump. */
  jump_px: number;
  /** Seconds trimmed inward from the edge of a stretch beside a pause, a jump or an epoch bound. */
  pause_margin_s: number;
  /** The longest heading gap filled along the shortest arc, in seconds. */
  heading_fill_s: number;
  /** The speed in m/s under which the rat is still, which lets a longer heading gap be held. */
  running_floor_m_per_s: number;
}

/** A session for the replay: its facts, what the engine draws, its saved review and the blocks the review or the rules make. */
export interface SessionHeader {
  session_id: string;
  subject_id: string;
  group: string;
  protocol: string;
  date: string;
  rate_hz: number;
  /** The lab's max gap in frames: lights unfilled for longer than this make a tracking gap. */
  max_gap: number;
  n_frames: number;
  in_dataset: boolean;
  reason: string | null;
  annotated_exclude: boolean;
  excluded: boolean;
  epochs: Epoch[];
  runs: Run[];
  rules: SessionRules;
  /** The epochs the rules cut into blocks. */
  selected_epochs: string[];
  n_initial_blocks: number;
  /** The geometry in metres of each environment of the session's epochs, by name. */
  environments: Record<string, Geometry>;
  frame: SessionFrame;
  /** The start offset in metres the session is registered with, none when the yaml's applies. */
  start_offset_m: number | null;
  /** The start offset the environment's yaml sets, in metres. */
  start_offset_default_m: number;
  heading_spans: { lost: HeadingSpan[]; filled: HeadingSpan[]; held: HeadingSpan[] };
  cut_points: CutPoint[];
  margins: Span[];
  stretches: Stretch[];
  occupancy: Occupancy;
  stops: Span[];
  /** What to know before trusting the session, including a review made under other rules and saved blocks that differ from today's. */
  warnings: string[];
  review: Review | null;
  blocks: MadeBlock[];
  refusals: Refusal[];
  cuts: Cut[];
  flagged_runs: number[];
}

// One typed array per column of the Arrow streams, one row per frame. The session's arrays are sent as float32 but t, the Workspace widens them to float64 when it reads them.
export interface SessionArrays {
  t: Float64Array;
  x: Float64Array;
  y: Float64Array;
  /** The smoothed position, for drawing only, NaN where the engine's window does not fit. */
  x_smooth: Float64Array;
  y_smooth: Float64Array;
  heading: Float64Array;
  speed: Float64Array;
  turn_rate: Float64Array;
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
  turn_rate: Float64Array;
  n_lights: Int8Array;
  trip: Int32Array;
}

/** The body of a preview: the whole edit list, the settings the window counts are at and the start offset the session is registered with, none for the yaml's. */
export interface PreviewBody {
  edits: Edit[];
  settings: WindowSettings;
  start_offset_m: number | null;
}

/** The body of a save: the whole edit list, the free text note and the settings the build's window counts are at. */
export interface SaveBody extends PreviewBody {
  notes: string;
}

export interface Preview {
  blocks: MadeBlock[];
  refusals: Refusal[];
  cuts: Cut[];
  flagged_runs: number[];
}

/** The outcome of building a session's blocks: how many were written, which failed and why, or the error that stopped the build. */
export interface Build {
  built: number;
  failed: { block_id: string; problems: string[] }[];
  build_error: string | null;
}

/** What writing a review answers: the review as written, whether it replaced an earlier one, and the file relative to the processed folder. */
export interface Saved {
  review: Review;
  replaced: boolean;
  file: string;
}

export interface SavedBlocks extends Saved, Build {}

/** What excluding or including a session answers: the save's shape, the review being none when including removed it, which it does for a review that only recorded the exclusion. */
export interface ExclusionSaved extends Build {
  review: Review | null;
  replaced: boolean;
  file: string;
  deleted: boolean;
}

export interface Rebuilt {
  /** Every review's outcome, an excluded session's build writes no blocks. */
  sessions: Record<string, Build>;
  /** The reviews of sessions the tool cannot work with (no frames, no epoch of the rules), not built, by session id with the reason. */
  skipped: Record<string, string>;
  /** The sessions the person excluded, by session id with the notes of their review. */
  excluded: Record<string, string>;
  totals: { sessions: number; built: number; failed: number; errors: number; skipped: number; excluded: number };
}

/** One row of the blocks index, a block as the build wrote it. */
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
  /** The rate the block was built at, in frames per second. */
  rate_hz: number;
  n_runs: number;
  n_clean_runs: number;
  n_trips: number;
  n_complete_trips: number;
  heading_lost_s: number;
  heading_filled_s: number;
  heading_held_s: number;
  scale_px_per_m: number;
  rotation_rad: number;
  led_offset_rad: number;
  kinematics_version: number;
}

export interface ReadinessBlock extends BlockRow {
  /** The windows the block yields at the settings. */
  count: number;
  verdict: Verdict;
}

export interface ReadinessTotals {
  blocks: number;
  ok: number;
  trouble: number;
  windows: number;
  windows_ok: number;
}

/** Readiness: every built block with its window count and verdict at the settings, judged under the rules its session was built with. */
export interface Readiness {
  which: string;
  settings: WindowSettings;
  blocks: ReadinessBlock[];
  totals: ReadinessTotals;
  /** Per built session, the settings and the time its blocks were built at, whether it was built excluded and the blocks that failed with their problems. */
  built: Record<string, BuiltSession>;
}

export interface BuiltSession {
  settings: WindowSettings;
  built_at: string;
  excluded: boolean;
  failed: { block_id: string; problems: string[] }[];
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

/** The registration a built session was given in an environment, for one epoch kind, as its build recorded it: angles in radians, lengths in metres, scales in pixels per metre. */
export interface RegisteredSession {
  session_id: string;
  kind: string;
  scale_px_per_m: number;
  led_separation_m: number;
  rotation_rad: number;
  flip: boolean;
  offset_m: [number, number];
  /** The two axis estimates of the scale, on a track only. */
  scale_x?: number;
  scale_y?: number;
  /** How far up the room's y axis the start site lies over the bottom outer corridor's occupancy peak, in metres, on a track only and missing from a build made before it was recorded. */
  start_offset_measured_m?: number;
  led_offset_rad: number;
  /** How concentrated the running frames' LED offsets are, 0 to 1. */
  led_offset_r: number;
  led_offset_n: number;
  warnings: string[];
  built_at: string;
}

/** An environment of the folder with its yaml parameters, geometry and the built sessions registered in it. */
export interface EnvironmentEntry {
  name: string;
  kind: string;
  params: Record<string, unknown>;
  geometry: Geometry;
  sessions: RegisteredSession[];
  summary: { n_sessions: number; n_warned: number };
}

/** A built block for the player. Every span holds indices into the block's arrays. */
export interface BlockHeader {
  row: BlockRow;
  /** The block's own rate, its frames over its seconds. */
  rate_hz: number;
  geometry: Geometry;
  runs: { run: number; path_id: number; clean: boolean; first: number; last: number }[];
  trips: { trip: number; partial: boolean; first: number; last: number }[];
  phases: { phase: string; first: number; last: number }[];
  heading_filled: Span[];
  heading_held: Span[];
  one_light: Span[];
}

/** Indices into the block's arrays with the stops exclusive, `stop` being the window's end plus its horizon, and the checks taken over that whole range. */
export interface BlockWindow {
  index: number;
  first: number;
  burn_in_stop: number;
  window_stop: number;
  stop: number;
  start_s: number;
  stop_s: number;
  /** The share of the frames with a finite position. */
  position_finite: number;
  heading_measured: number;
  /** The trips whose outbound start and return end both lie inside the window and its horizon. */
  trips_complete: number;
  /** The other trips touching that range: cut by it or by the end of the block. */
  trips_partial: number;
  ok: boolean;
  /** The first check the window fails, none when it passes. */
  reason: string | null;
}

export interface BlockWindows {
  rows: BlockWindow[];
  verdict: Verdict;
  count: number;
}

/** The window settings selected for export with the readiness totals they gave, none when none were selected. */
export interface Selected {
  selected: { settings: WindowSettings; totals: ReadinessTotals; selected_at: string; selected_by: string } | null;
}

export interface SelectedResult {
  replaced: boolean;
  file: string;
}

export interface FormatColumn {
  name: string;
  type: string;
  required: boolean;
}

/** A file an access declares. A review file also lists its block keys, statuses and the fields of each edit. */
export interface FormatFile {
  path: string;
  optional: boolean;
  columns?: FormatColumn[];
  keys?: string[];
  block_keys?: string[];
  statuses?: string[];
  edits?: Record<string, string[]>;
}

export interface FormatContract {
  version: number;
  transformed: { files: FormatFile[] };
  processed: { files: FormatFile[] };
  synthetic: { files: FormatFile[] };
  /** The default window settings. */
  settings: WindowSettings;
  /** The engine's rules with their values, in the engine's order. */
  rules: Record<string, unknown>;
}

// The synthetic sets and the quiz, from managers/synthesis.py and engines/trajectory/recipe.py.

/** One row of the sets index: when and by whom the set was made, what it drew on, what it holds and how the guesses against it stand. */
export interface SetRow {
  set_id: string;
  created_at: string;
  created_by: string;
  sources: string[];
  seed: number;
  /** The seconds generated per epoch kind. */
  length_s: Record<string, number>;
  n_blocks: number;
  kinds: string[];
  n_guesses: number;
  n_correct: number;
}

/** A distribution as the recipe summarises it, every entry null when there were no values. */
export interface Quantiles {
  q05: number | null;
  q25: number | null;
  q50: number | null;
  q75: number | null;
  q95: number | null;
  mean: number | null;
}

/** The recipe of the blocks of one kind: the numbers the generator fits and real and synthetic blocks are compared on. The track and arena keys are each kind's own. */
export interface Recipe {
  counts: { blocks: number; frames: number; seconds: number };
  speed: Quantiles;
  turn_rate: Quantiles;
  turn_rate_abs_mean: number | null;
  still_fraction: number | null;
  heading_spread_rad: number | null;
  pauses: { per_min: number; duration_s: Quantiles };
  phase_share: Record<string, number>;
  /** Both kinds: the per frame tracking noise in metres, from the spread of the position's second difference, and the turns of the direction of motion by over 120 degrees in half a second per minute. */
  tracking_noise_m?: number | null;
  reversals_per_min?: number;
  /** Track: the runs per path id, the speed variation within a run, the distance from the centreline over running frames (unsigned, and signed outward on the perimeter and the inner segments), the reversals inside a run per minute, the dwells per site, the trips per minute and the share of outbound runs per goal. */
  runs?: Record<string, { count: number; duration_s: Quantiles }>;
  speed_cv_run?: number | null;
  lateral_m?: Quantiles;
  lateral_outward_m?: { perimeter: Quantiles; inner: Quantiles };
  run_reversals_per_min?: number;
  dwell_s?: Record<string, Quantiles>;
  trips_per_min?: number;
  goal_share?: Record<string, number>;
  /** Arena: its environment, the speed variation within a running stretch, the distance to the boundary and the occupancy over the room's grid. */
  environment?: string;
  speed_cv?: number | null;
  boundary_distance_m?: Quantiles;
  occupancy_grid?: number[][];
}

/** The recipes by kind, a kind with no blocks absent. */
export type Recipes = Record<string, Recipe>;

/** What a set records about how it was made. */
export interface Provenance {
  set_id: string;
  created_at: string;
  created_by: string;
  sources: string[];
  environments: Record<string, string>;
  camera: Record<string, unknown>;
  seed: number;
  length_s: Record<string, number>;
  rules: Record<string, unknown>;
  settings: WindowSettings;
  code_version: string;
  generator: { version: number };
  recipe_real: Recipes;
  recipe_synthetic: Recipes;
  warnings: string[];
  failed: { block_id: string; problems: string[] }[];
}

export interface SetHeader extends Provenance {
  blocks: BlockRow[];
}

/** The body of a generate: the source sessions, the seed, the seconds per epoch kind and the settings recorded in the provenance. */
export interface GenerateBody {
  sources: string[];
  seed: number;
  length_s: Record<string, number>;
  settings: WindowSettings;
}

export interface Generated {
  set_id: string;
  built: number;
  failed: { block_id: string; problems: string[] }[];
  warnings: string[];
  kinds: string[];
}

export interface DeletedSet {
  deleted: boolean;
  blocks: number;
}

export type Side = "left" | "right";

/** An open quiz pair: its opaque id, the kind of both blocks and the two sides to read. */
export interface Pair {
  pair_id: string;
  kind: string;
  sides: Side[];
}

/** One side of a pair as the quiz player's header, only what both sides share. */
export interface PairHeader {
  row: { kind: string; environment: string; n_frames: number; duration_s: number; rate_hz: number };
  rate_hz: number;
  geometry: Geometry;
}

export interface PairArrays {
  x: Float64Array;
  y: Float64Array;
  heading: Float64Array;
  speed: Float64Array;
}

export interface Tally {
  n: number;
  correct: number;
  by: Record<string, { n: number; correct: number }>;
}

/** One guess as the set's guesses.json holds it, guessed_real being the block the person called real. */
export interface Guess {
  at: string;
  by: string;
  pair_id: string;
  real_block: string;
  synthetic_block: string;
  kind: string;
  guessed_real: string;
  correct: boolean;
}

/** The reveal after a guess: whether it was right, which side and blocks were which, and the set's tally. */
export interface Reveal {
  correct: boolean;
  real_side: Side;
  real_block: string;
  synthetic_block: string;
  tally: Tally;
}

export interface SetGuesses {
  tally: Tally;
  guesses: Guess[];
}

// The parts of FastAPI's OpenAPI document the About page reads.
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
