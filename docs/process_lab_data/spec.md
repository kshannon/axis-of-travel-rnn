# Lab data clean

Stage 2 of the lab data: turn the converter's tables (stage 1, `docs/transform_lab_data/`) into
continuous, labelled trajectories in metres, the validation set for a trained network and the
source of the statistics the synthetic generator is fitted to. Everything is written outside
the repository under `PROCESSED_LAB_DATA` in `configs/local.yaml`.

## Out of Scope

- Statistics and the recipe file (stage 3, `docs/synthetic_data/`), RatReplay and its review files
  (`docs/ratreplay/`), the synthetic generator and of course training an RNN.
- Resampling: blocks stay at the native 60 Hz, to be downsampled on the fly.
- Rotation, infusion and dark sessions, and JL1HPCData (a different apparatus until confirmed).
  The baseline epochs of rotation sessions can be added later as a test set.
- Registration beyond scale, flip, rotation and translation: the triple-T geometry is not
  fitted. The config `triple_t.yaml` is fine for the time being.

## Overview

A block is one continuous stretch of one epoch with no pause and no tracking gap: the unit an
RNN can run through without a jump. The track epoch of a session yields a few long blocks that
hold many runs back to back, returns and reward dwells included. The arena epoch yields forage
blocks. Nothing is trimmed to a run: labels mark the runs, and training drops what it does not
want (preprocessing stage in training pipeline). Two datasets, `track/` and `arena/`, same
columns, built separately.

## Functional Requirements

### Inputs

`sessions.csv`, `epochs.csv`, `runs.csv`, `events.csv`, `frames/*.parquet` and `manifest.json`
from `TRANSFORMED_LAB_DATA`. Also `annotations.csv` when present, and the review files
`PROCESSED_LAB_DATA/review/<session_id>.json` written by RatReplay (`docs/ratreplay/`): a reviewed
session builds exactly its confirmed blocks, with its cuts applied and its flagged runs unlabelled,
an unreviewed session gets the automatic cuts, and the manifest says which.

### Selection, named constants in the script

Sessions: `protocol == standard`, not `exclude` in annotations, group not JL1HPCData. Epochs:
`arena` and `track` with `condition == baseline`. A block is cut at every pause (a step in `t`
over 0.1 s), at every stretch with both lights unfilled for more than `max_gap` frames (decided
2026-10-14 from the dry runs, see blocks.md: cutting on either light fragmented the track into
15 s pieces), at every position jump over `JUMP_PX` 40 px in one frame (a tracking teleport, the
worst thing a training window can hold), and at the epoch bounds. `PAUSE_MARGIN_SEC` 5 s is
trimmed around every pause and jump and at both ends of every epoch, where the rat is being
placed or lifted out. Position is never interpolated. Heading, a label only, never cuts a block:
gaps up to `HEADING_FILL_SEC` 3 s (one LED lost, mostly while eating) are filled by circular
linear interpolation and flagged `heading_filled`. A longer gap during which the rat stays under
the running floor (3 cm/s, the head in a reward well) is filled by holding the last heading and
flagged `heading_held`. Other long gaps stay NaN and flagged. `turn_rate` is derived from the
measured heading only and is NaN on filled or held frames, so a fill never becomes a turn. A trip
is complete when its outbound run and its return run both lie inside the block, the dwell after
the return is part of it when present. Blocks
shorter than 10 s are dropped (proposal to settle
after the first reviews: one full trip, about 20 s, on the track, since a block shorter than a
trip holds no training window, and 10 s in the arena). Runs keep the lab's `clean` flag
and a run flagged `duplicate_of` keeps only its first occurrence. `overlap_frames` is applied by the
cut rule defined in tables.md 3.1. The counts surviving each step are printed and written to the manifest.

### Frame conversion

Per session and epoch: pixel scale from the track geometry (160 by 125 cm, Olson 2017, the
distance between the outer corridor centrelines found as occupancy peaks), the arena from the
same session's track scale corrected by the parallax ratio (the arena floor is 20 cm higher).
The median LED separation per session is written to the manifest as a check, not used as the
scale: on the real data it is about 6.8 cm for NS14 and 6 cm for NS15 and NS16, not the paper's
5 cm (decided 2026-10-15). Position is the lab's mashup light: the midpoint of
the two LEDs, or the one good LED when the other is lost, with `n_lights` (2 or 1) per frame
saying which. `y` flipped so north is up, heading converted from camera convention (LED2 to
LED1, y down) to the convention (0 along +x, counterclockwise) and then rotated by the session's
LED offset, the circular mean of heading minus motion direction over running frames (about 110
degrees, the LEDs are not mounted along the body axis), so 0 is the direction of travel on
average. Heading is NaN where one LED is lost.
The track rotated so its axes align with the room axes and translated so the start site maps
to the config's start. Scale, flip, rotation and offset go in the manifest per session.

### Outputs, under `PROCESSED_LAB_DATA`

`track/blocks.csv` and `arena/blocks.csv`, one wide row per block: `block_id`, `session_id`,
`subject_id`, `date`, `environment`, `epoch`, `frame_start`, `frame_end`, `duration_s`,
`n_runs`, `n_clean_runs`, `scale_px_per_m`, why it survived. `track/blocks/<block_id>.parquet`
and `arena/blocks/<block_id>.parquet`, one row per 60 Hz frame, the trajectory schema
(`docs/trajectory/spec.md`, revised here): `t`, `x`, `y` (m), `heading` (rad), `speed`,
`turn_rate` (derived by the one versioned function: smooth, then difference), `n_lights`, `heading_filled`, `heading_held`,
`filled_front`, `filled_back`, `phase` (outbound, dwell, return, pause, forage), `trip`, `run`, `path_id`, `clean`.
`manifest.json`: rules and constants, per-session frame parameters, the funnel counts, the
converter manifest's timestamp.

### Runs, trips and phase labels

A run is one hand-clicked traversal of one labelled path, start click to end click, outbound
(paths 1 to 4, start to a goal) or return (paths 9 and 10, the perimeter back to the start), as
`runs.csv` holds it. A trip is an outbound run, the dwell at the goal, the return run and the
dwell at the start, labelled per frame as `trip` (a trip cut by a block boundary is marked
partial, its frames stay). `phase`: `outbound` and `return` from the lab's path ids, `dwell`
between an outbound end and the next return start or between a return end and the next
outbound start, `pause` where speed stays below 3 cm/s for over 1 s inside a run, `forage` in
the arena. Checked by eye in RatReplay, never edited per run. Block edges snap to trip
boundaries (the start-site dwell) where a cut allows it.

### Checks

No NaN in `x` or `y` inside a block, `t` steps equal 1/60 s, a block lies inside its
epoch, the track scale's x and y estimates within 5 percent of each other (a missed corridor peak
otherwise) and the implied LED separation between 4 and 8 cm (both warn), runs in `runs.csv` and
`run` labels agree, and finally every selected frame is in exactly one block.

## Non-Functional Requirements

`src/process_lab_data/` in the shape of the converter: `__main__.py`, named values at the top of
each file, one-line docstrings, `pixi run process-lab-data`, `--dry-run`, exit 0, 1 (a session failed a
check) or 2 (setup). pyarrow, numpy and scipy (Savitzky-Golay, peak finding) only. Tests on small synthetic tables: block cutting at
pauses and gaps, the frame conversion on known points, phase labels on a scripted run.
