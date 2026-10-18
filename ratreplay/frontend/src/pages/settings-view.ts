import type { Selected, WindowSettings } from "../api/types";
import { percent } from "../ui/format";
import { counted, settingsText } from "../ui/text";
import { stampWithSince } from "../ui/time";

/** One window setting as an input: its label, the step of its arrows and the one line of what it protects. */
export interface SettingField {
  key: keyof WindowSettings;
  label: string;
  step: string;
  hint: string;
}

/** The seven window settings in the order they are read. The defaults are not here, the API gives them. */
export const SETTING_FIELDS: readonly SettingField[] = [
  { key: "window_s", label: "window (s)", step: "1", hint: "The slice of a block the network sees." },
  { key: "stride_s", label: "stride (s)", step: "0.5", hint: "How far the next window starts." },
  { key: "burn_in_s", label: "burn-in (s)", step: "0.5", hint: "The opening seconds the network warms up on." },
  { key: "horizon_s", label: "horizon (s)", step: "0.5", hint: "How far ahead the position is predicted." },
  { key: "rate_hz", label: "training rate (Hz)", step: "1", hint: "The rate the RNN project resamples to, unused here." },
  {
    key: "min_heading_measured", label: "min measured heading", step: "0.05",
    hint: "The share of a block's head direction that must be measured, not filled, so the validation of the network's axis tuning rests on real heading.",
  },
  { key: "min_complete_trips", label: "min complete trips", step: "1", hint: "A track block must hold this many whole outbound and return trips." },
];

export interface FieldRow extends SettingField {
  /** The default as the API gives it, written plainly. */
  default: string;
}

/** The fields with the default of each beside them, blank until the defaults arrive. */
export function fieldRows(defaults: WindowSettings | null): FieldRow[] {
  return SETTING_FIELDS.map((field) => ({ ...field, default: defaults ? String(defaults[field.key]) : "" }));
}

/** Whether every setting is its default. */
export function atDefaults(settings: WindowSettings, defaults: WindowSettings | null): boolean {
  return defaults !== null && SETTING_FIELDS.every(({ key }) => settings[key] === defaults[key]);
}

/** One setting beside the one it is compared with. */
export interface SettingRow {
  label: string;
  tried: string;
  built: string;
  differs: boolean;
}

/** Every setting in use beside the one a session was built with, marked where they differ. */
export function compareSettings(tried: WindowSettings, built: WindowSettings): SettingRow[] {
  return SETTING_FIELDS.map(({ key, label }) => ({ label, tried: String(tried[key]), built: String(built[key]), differs: built[key] !== tried[key] }));
}

/** The settings in a short line for a table cell or the line on the Blocks page. */
export function settingsLine(s: WindowSettings): string {
  return `${s.window_s} s window, ${s.stride_s} s stride, ${s.burn_in_s} s burn-in, ${s.horizon_s} s horizon, ${s.rate_hz} Hz, ` +
    `min ${percent(s.min_heading_measured)} heading measured, min ${counted(s.min_complete_trips, "complete trip")}`;
}

/** The line on the Blocks page saying which settings the verdicts are judged at. */
export function judgedLine(s: WindowSettings): string {
  return `judged at: ${settingsLine(s)}`;
}

/** The sentence under the fields saying what the verdicts are tested at. */
export function testedLine(s: WindowSettings): string {
  return `Verdicts at a ${s.window_s} s window plus a ${s.horizon_s} s horizon every ${s.stride_s} s, measured heading at least ${percent(s.min_heading_measured)}, a track block with at least ${counted(s.min_complete_trips, "complete trip")}.`;
}

/** The line saying which settings the export reads, none when none were selected. */
export function selectedLine(selected: Selected["selected"]): string {
  if (!selected) return "No settings are selected for export yet.";
  const { settings, totals, selected_at, selected_by } = selected;
  return `Selected for export ${stampWithSince(selected_at)} by ${selected_by}: ${settingsText(settings)}. They gave ${totals.ok} of ${counted(totals.blocks, "block")} ok and ${counted(totals.windows_ok, "window")} in them.`;
}

/** What each of the engine's rules does, in one line. A rule the engine gains and this lacks is listed with no meaning. */
const MEANINGS: Record<string, string> = {
  condition: "The condition whose epochs are cut into blocks.",
  epochs: "The epoch kinds cut into blocks.",
  pause_step_s: "A step in time over this many seconds is a pause in the recording.",
  gap_lights: "Whether both lights or either must be lost for a tracking gap.",
  jump_px: "A step in position over this many pixels is a tracking jump.",
  pause_margin_s: "Seconds trimmed inward from a stretch edge beside a pause, a jump or an epoch bound.",
  min_block_s: "The shortest block kept, in seconds.",
  snap_s: "How close in seconds a moved block edge snaps to the start or end of a run.",
  heading_fill_s: "The longest gap in head direction filled along the shortest arc, in seconds.",
  running_floor_m_per_s: "The speed in metres per second under which the rat is still, which holds a longer heading gap and labels a pause.",
  outbound_paths: "The lab's path ids of the outbound runs.",
  return_paths: "The lab's path ids of the return runs.",
  pause_min_s: "The shortest stillness in a run that counts as a pause, in seconds.",
  histogram_bin_px: "The bin of the position histogram the track scale is read from, in pixels.",
  peak_smooth_bins: "The bins the peaks of that histogram are smoothed over.",
  peak_prominence: "How far a peak of the histogram must stand out to count.",
  axis_agree: "How closely the scales of the two track axes must agree.",
  camera_height_m: "The height of the camera in the parallax ratio between arena and track, in metres.",
  track_height_m: "The height of the track in the parallax ratio, in metres.",
  arena_height_m: "The height of the arena in the parallax ratio, in metres.",
  nominal_led_separation_m: "The paper's separation of the two lights, used by the still floor, in metres.",
  extent_percentiles: "The percentiles of the arena's moving positions that give its extent.",
  led_separation_m: "The range in metres the light separation of a kind must fall in, else a warning.",
  speed_smooth_frames: "The frames averaged for speed and direction.",
  running_px_per_s: "The speed in pixels per second that counts as running.",
  offset_warn_deg: "The degrees from a rat's median offset over which its lights are reported swapped.",
  t_step_tolerance_s: "The most a step in time may differ from one frame before a block reports a problem.",
  smooth_window_s: "The window in seconds of the Savitzky-Golay smoothing of position.",
  smooth_order: "The order of the Savitzky-Golay smoothing.",
  kinematics_version: "Names this derivation of speed and direction in a build.",
};

export interface RuleRow {
  name: string;
  value: string;
  meaning: string;
}

/** A rule's value written plainly: a list joined by commas. */
function valueText(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : String(value);
}

/** The engine's rules as rows in the engine's order, each with its value and meaning. */
export function ruleRows(rules: Record<string, unknown>): RuleRow[] {
  return Object.entries(rules).map(([name, value]) => ({ name, value: valueText(value), meaning: MEANINGS[name] ?? "" }));
}
