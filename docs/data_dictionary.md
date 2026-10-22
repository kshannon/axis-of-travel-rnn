# Data dictionary

The files the block step reads and writes, as `src/axis_of_travel_rnn/blocks/` writes them (engine version 2, review format version 4).
The lab's variables and the transformed tables are in `docs/transform_lab_data/tables.md`. Conventions: time in seconds, positions in
metres in the room frame (1.8 by 1.8 m, origin at the bottom left, x to the east, y to the north), angles in radians, `session_id` on
every row and in every file name. Columns and keys are listed in the order the files hold them.

## The three folders

| folder | named by | written by | holds |
|---|---|---|---|
| transformed | `TRANSFORMED_LAB_DATA` in `configs/local.yaml` | `pixi run transform-lab-data` | the lab's data as tables and one frames parquet per session. Read only here. Documented in `docs/transform_lab_data/tables.md` section 2, not repeated |
| reviews | `reviews` in the blueprint, `data/reviews` | the review tool, by the person | one json file per session, committed |
| built | `PROCESSED_LAB_DATA` in `configs/local.yaml` plus the blueprint's name | `pixi run build-blocks --blueprint <name>` | `PROCESSED_LAB_DATA/<blueprint>/`, outside the repository, never committed |

The build reads `sessions.csv`, `epochs.csv`, `runs.csv`, `annotations.csv` (optional), `frames/{sid}.parquet` and the converter's `manifest.json`,
whose `run.timestamp` is the transformed stamp. The lab's MATLAB files (`LAB_DATA`) feed only the transform.

## Reviews: `data/reviews/{sid}.json`

Written whole by the review tool. A session with no file is listed as skipped. A key an older file lacks takes the default in brackets.

| key | meaning | person's decision |
|---|---|---|
| `session_id` | the session | no |
| `reviewed_by`, `reviewed_at` | who saved the review and when (ISO time), null until saved | no, the record |
| `converter_manifest_timestamp` | the transformed run the review was made against | no, the record |
| `rules` | the rules in force when it was saved, a mismatch with the build's rules gives the warning "reviewed under other rules" | no, the record |
| `blocks` | the blocks, each `block_id`, `epoch`, `environment`, `frame_start`, `frame_end`, `status` (`auto`, `confirmed`, `edited`, `dropped`) and `note`. The build keeps `confirmed` and `edited` | yes |
| `cuts` | frame ranges cut out, each with `frame_start`, `frame_end` and `reason`. Already applied in `blocks`, not read by the build | yes |
| `flagged_runs` | run numbers left out of the labels, so their frames take run 0 | yes |
| `notes`, `edits` | free text, and the ordered edit list (`accept`, `confirm`, `move`, `split`, `drop`, `new`, `cut`, `trips`, `flag`) that made the blocks. Not read by the build | yes |
| `excluded` (false) | the session is left out, the build writes no blocks | yes |
| `excluded_by`, `excluded_at` (null) | who set the exclusion and when | no, the record |
| `start_offset_m` (null) | metres the person tuned for the start site of `triple_t`, null meaning the environment yaml's | yes |

## Built folder: `PROCESSED_LAB_DATA/<blueprint>/`

```
manifest.json            how it was built, with the data id
blocks.csv               one row per block
blocks/{block_id}.parquet   one row per frame of the block
metadata/{sid}.json      what each session's build used
```

`block_id` is `{session_id}_{epoch}_{NN}`, NN counting the epoch's blocks in frame order from 01, dropped ones included, so a built session can skip a number.
A block is a stretch of one epoch with no pause, tracking jump or long gap inside it, trimmed `pause_margin_s` from them, kept by the person.

### `blocks/{block_id}.parquet`, at the lab rate (60 Hz)

| column | type | unit | meaning |
|---|---|---|---|
| `frame` | int32 | frame | the lab's frame number, 1-based, a row maps back to the transformed frames table |
| `t` | float64 | s | time from the block's first frame, one frame per step |
| `x`, `y` | float64 | m | the mashup light in the room frame: y negated for the camera, divided by the scale, rotated by the track rotation, shifted by the offset (metadata `frame`) |
| `heading` | float64 | rad | the head direction, see the convention below. NaN where lost |
| `speed` | float64 | m/s | Savitzky-Golay derivative of `x`, `y` (`smooth_window_s`, `smooth_order`) over the block alone. NaN where position is missing |
| `turn_rate` | float64 | rad/s | the same derivative of the unwrapped measured heading, counterclockwise positive, the head's angular velocity. NaN wherever heading is not measured (lost, filled, held) and in measured stretches shorter than the window |
| `n_lights` | int8 | count | lights the lab did not leave unfilled, 2, 1 or 0 |
| `heading_filled` | bool | | heading is the engine's fill along the shortest arc across a gap of up to `heading_fill_s` |
| `heading_held` | bool | | heading is held at its last measured value across a longer gap, the rat being still throughout |
| `filled_front`, `filled_back` | bool | | the lab interpolated that light on this frame |
| `phase` | string | | `outbound`, `dwell`, `return`, `pause` or `forage`, below |
| `trip` | int32 | | trip number, positive when complete, negative when partial, 0 in the arena, below |
| `run` | int32 | | the transformed runs table's `run` (1-based in start order), 0 outside any run. Where runs overlap the later one owns the frames, duplicates and flagged runs are left out |
| `path_id` | int16 | | the lab's path id of the run, 0 outside any run. 1 to 4 are the outbound paths and 9 and 10 the returns |
| `clean` | bool | | the labeler's judgment of the run, copied from the runs table, false outside any run. What it means depends on the labeling tool (tables.md 1.2) |

Heading convention: the angle of the head in the room frame, counterclockwise from east, so north is pi over 2, wrapped to minus pi up to pi. It is the lab's
camera heading negated (the camera's y points down), minus the session's LED offset (the fixed angle of the light bar on the head, so that heading minus the
direction of travel averages 0 over running frames), plus the track rotation. It is where the head points, not the direction of travel.

Phase, one label per frame, the first rule that applies: `forage` on every frame of an arena block. `pause` inside a run where speed stays under `running_floor_m_per_s`
for over `pause_min_s`. `outbound` or `return` inside a run whose `path_id` is in `outbound_paths` or `return_paths`. `dwell` on all other track frames (at a reward site, between runs,
before the first run, after the last, or in a run of another path).

Trip: an outbound run, the dwell at the goal, the return run and the dwell at the start, from one outbound start to the next or to the block end. It is complete when its outbound
run and its return run (the first one starting before the next outbound) both lie inside the block. Any other trip is partial and negative: the frames before the first outbound start
(trip -1 when the block does not open on one, the first outbound start then opens trip 2), or a trip the block end cuts or that has no return.

### `blocks.csv`, one row per block, sorted by session

| column | type | unit | meaning |
|---|---|---|---|
| `block_id` | str | | as above, the parquet's file name |
| `session_id`, `subject_id`, `protocol` | str | | from the sessions table. `protocol` is `standard`, `rotation`, `infusion`, `dark` or `other` |
| `date` | str | | recording date, YYYY-MM-DD |
| `environment` | str | | the environment yaml of the block's epoch, `open_arena` or `triple_t` |
| `epoch`, `kind` | str | | `track` or `arena`, the same value in both columns |
| `frame_start`, `frame_end` | int | frame | first and last lab frame, 1-based, inclusive |
| `n_frames`, `rate_hz` | int | frames, Hz | rows in the parquet and the lab rate |
| `duration_s` | float | s | `n_frames` over `rate_hz` |
| `n_runs`, `n_clean_runs` | int | count | distinct run numbers in the block, and those marked clean |
| `n_trips`, `n_complete_trips` | int | count | distinct trips, partial included, and complete ones |
| `heading_lost_s`, `heading_filled_s`, `heading_held_s` | float | s | time with heading missing, filled and held |
| `status` | str | | the review's status of the block, `confirmed` or `edited` |
| `reviewed_by` | str | | the review's `reviewed_by` |
| `scale_px_per_m` | float | px/m | the registration scale of the block's kind (the arena's is the track's times the parallax ratio of the three heights) |
| `rotation_rad` | float | rad | the track rotation, counterclockwise, used for both kinds |
| `led_offset_rad` | float | rad | the session's LED offset |
| `kinematics_version` | int | | the `kinematics_version` rule the block's speed and turn rate were derived under |

### `metadata/{sid}.json`, one per built session, written whole

| key | meaning |
|---|---|
| `rules`, `settings` | the full rules and settings used, defaults with the blueprint's overrides |
| `review_stamp` | `reviewed_at` and `converter_manifest_timestamp` of the review |
| `code_version` | `blocks <engine version> <short commit>`, with `+dirty` when tracked files had changes, `unknown` without git |
| `built_at` | UTC time to the second |
| `windows` | per block, `count` of windows and a `verdict` (`ok`, `reasons`) at these settings. Informative, windows are not stored |
| `frame` | the registration: `led_offset_rad`, `led_offset_r` (concentration), `led_offset_n` (running frames used), `start_px`, `goals_px`, and per kind (`track`, `arena`) `scale_px_per_m`, `led_separation_m`, `rotation_rad`, `rotation_concentration`, `flip`, `offset_m`. The track adds `scale_x_px_per_m`, `scale_y_px_per_m`, `start_offset_measured_m`, the arena `arena_extent_ratio`. Null when excluded |
| `warnings` | strings: scale estimates that disagree, LED separation out of range, reviewed under other rules |
| `failed` | blocks not written, each `block_id` and its `problems` (position not finite, irregular steps in `t`) |
| `excluded` | the review excluded the session, so it has no blocks |
| `start_offset_m` | the start offset it was built with, null for the yaml's |

### `manifest.json`

| key | meaning |
|---|---|
| `blueprint` | `name`, `sha256` of the blueprint file, `format_version` |
| `data_id` | the id of the blocks, below |
| `transformed_stamp` | `run.timestamp` of the transformed folder's manifest |
| `git_commit`, `package_version`, `engine_version`, `built_at` | the short commit (`+dirty`, `unknown`), `axis_of_travel_rnn.__version__`, `blocks.VERSION`, UTC time |
| `counts` | `sessions_built`, `blocks_written`, `failed_blocks`, `skipped_sessions`, `excluded_sessions`, `errors` |
| `failed`, `skipped`, `excluded`, `errors` | failed blocks by session, skipped sessions with the reason (no review file, not in the transformed folder, or the funnel's), excluded session ids, and sessions whose build raised, with the message |

The data id is the sha256 over blocks.csv, then every block parquet in block id order, one line each: the path inside the build folder (`blocks.csv`, `blocks/{block_id}.parquet`), a space, the
sha256 of the file's bytes, and a newline. Metadata and manifest are outside it, so rebuilding the same blocks gives the same id on any day. It hashes bytes, so a different pyarrow can change it
while the values stay equal, `scripts/compare_blocks.py OLD NEW` then compares by content. A build exits 1 when it differs from the blueprint's `expected_data_id`.

## Blueprint: `configs/blueprints/{name}.yaml`

Read by `blocks/blueprint.py`, which refuses an unknown key, an unknown rule or setting name, and a wrong type.

| key | default | meaning |
|---|---|---|
| `name` | required | names the built folder |
| `format_version` | required | the review tool's format version the reviews and blocks follow. Recorded in the manifest, not checked |
| `description` | empty | free text |
| `transformed` | required | the `configs/local.yaml` key of the transformed folder, `TRANSFORMED_LAB_DATA` |
| `reviews` | required | the reviews folder, relative to the repository |
| `sessions` | required | `all_reviewed` (every file in the reviews folder) or a list of session ids |
| `rules` | `{}` | overrides over the rules below |
| `settings` | `{}` | overrides over the settings below |
| `start_offsets` | `from_reviews` | or session id to metres, sessions not listed taking their review's |
| `expected_data_id` | null | the data id a build must give, set after the first build |

## Rules and settings

Rules shape the blocks, their defaults are `RULES` in `blocks/__init__.py`, grouped as the code groups them.

- Epochs cut: `condition` baseline, `epochs` (arena, track).
- Cut points: `pause_step_s` 0.1, `gap_lights` both, `jump_px` 40.0.
- Blocks: `pause_margin_s` 5.0, `min_block_s` 10.0, `snap_s` 1.0.
- Heading: `heading_fill_s` 3.0, `running_floor_m_per_s` 0.03.
- Labels: `outbound_paths` (1, 2, 3, 4), `return_paths` (9, 10), `pause_min_s` 1.0.
- Track scale: `histogram_bin_px` 2.0, `peak_smooth_bins` 5, `peak_prominence` 0.1, `axis_agree` 0.05.
- Arena against track: `camera_height_m` 2.6, `track_height_m` 0.2, `arena_height_m` 0.4.
- LEDs: `nominal_led_separation_m` 0.05, `extent_percentiles` (1, 99), `led_separation_m` (0.04, 0.08).
- Motion: `speed_smooth_frames` 6, `running_px_per_s` 20.0, `offset_warn_deg` 30.0 (not read by any code today).
- Checks: `t_step_tolerance_s` 1e-6.
- Kinematics: `smooth_window_s` 0.15, `smooth_order` 2, `kinematics_version` 1.

Settings (`SETTINGS`) give each block its window count and verdict in the metadata, nothing else is stored: `window_s` 40.0, `stride_s` 10.0, `burn_in_s` 1.0, `horizon_s` 0.5,
`rate_hz` 20 (recorded only, windows work at the block's rate), `min_heading_measured` 0.8, `min_complete_trips` 1.

## What reaches training and what never does

The network's inputs are an experiment choice, the `inputs.columns` of its config (AGENTS.md rule 1). `dataset.ALLOWED_INPUTS` is the whole list and the config refuses any other column.

| input column | network inputs | scaling |
|---|---|---|
| `x`, `y` | one each | standardised by the mean and sd of the training blocks |
| `speed` | one | the same |
| `turn_rate` | one | the same |
| `heading` | two, `heading_sin` and `heading_cos`, the sine and cosine of the angle | none, they lie within minus one and one |

Position only (`x`, `y`) is the default and the control (`configs/experiments/baseline.yaml`). `configs/experiments/biological.yaml` adds `speed`, `heading` and `turn_rate`, six network inputs.
`heading` and `turn_rate` are measured signals, the head direction and the head's angular velocity, so a config may name them. A frame with no heading gives NaN in both heading columns and in
`turn_rate`, and `turn_rate` is also NaN where heading is filled or held. A window holding such a frame is left out of the dataset and counted (`WindowDataset.skipped`). The target is the
future position `x`, `y` in every experiment.

Never reaches training: `phase`, `trip`, `run`, `path_id`, `clean`, axis labels, cell type, and any hand coded direction of travel. They stay in the data for validation, controls and post hoc analysis.
A control that needs one must say so in its config. The remaining columns (`n_lights`, the fill flags) describe quality and are not inputs. `min_heading_measured` and `min_complete_trips` use heading and trips
to choose which windows qualify, which selects data and feeds nothing to the network.
