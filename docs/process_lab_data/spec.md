# Lab data clean

Stage 2 of the lab data: turn the converter's tables (stage 1, `docs/transform_lab_data/`) into
continuous, labelled trajectories in metres, the validation set for a trained network and the
source of the statistics the synthetic generator is fitted to. Everything is written outside
the repository under `PROCESSED_LAB_DATA` in `configs/local.yaml`.

## Out of Scope

- Statistics and the recipe file (stage 3, `docs/synthetic_data/`), the viewer and verdicts
  (`docs/trajectory_viewer/`), the synthetic generator and of course training an RNN.
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
from `TRANSFORMED_LAB_DATA`. Also `annotations.csv` when present, and `verdicts.csv` (by hand, from the
viewer, keyed by `block_id` or `(session_id, run)`) when present.

### Selection, named constants in the script

Sessions: `protocol == standard`, not `exclude` in annotations, group not JL1HPCData. Epochs:
`arena` and `track` with `condition == baseline`. A block is cut at every pause (a step in `t`
over 0.1 s), at every stretch with either light unfilled for more than `max_gap` frames, and at
the epoch bounds. Also blocks shorter than 10 secs will be dropped. Runs keep the lab's `clean` flag
and a run flagged `duplicate_of` keeps only its first occurrence. `overlap_frames` is applied by the
cut rule defined in tables.md 3.1. The counts surviving each step are printed and written to the manifest.

### Frame conversion

Per session and epoch: pixel scale from the median LED separation (5 cm, Olson 2017), fitted
separately for track and arena (parallax), `y` flipped so north is up, heading converted from
camera convention (LED2 to LED1, y down) to the convention (0 along +x, counterclockwise).
The track rotated so its axes align with the room axes and translated so the start site maps
to the config's start. Scale, flip, rotation and offset go in the manifest per session.

### Outputs, under `PROCESSED_LAB_DATA`

`track/blocks.csv` and `arena/blocks.csv`, one wide row per block: `block_id`, `session_id`,
`subject_id`, `date`, `environment`, `epoch`, `frame_start`, `frame_end`, `duration_s`,
`n_runs`, `n_clean_runs`, `scale_px_per_m`, why it survived. `track/blocks/<block_id>.parquet`
and `arena/blocks/<block_id>.parquet`, one row per 60 Hz frame, the trajectory schema
(`docs/trajectory/spec.md`, revised here): `t`, `x`, `y` (m), `heading` (rad), `speed`,
`turn_rate` (derived by the one versioned function: smooth, then difference), `filled_front`,
`filled_back`, `phase` (outbound, dwell, return, pause, forage), `run`, `path_id`, `clean`.
`manifest.json`: rules and constants, per-session frame parameters, the funnel counts, the
converter manifest's timestamp.

### Phase labels, first rule, to be checked in the viewer

`outbound` from a run's start to its end click. `dwell` from the end click until speed rises
above 3 cm/s. `return` from then until the next run's start click or the start site. `pause`
wherever speed stays below 3 cm/s for over 1 s outside a dwell. `forage` in the arena.

### Checks

No NaN in `x`, `y` or `heading` inside a block, `t` steps equal 1/60 s, a block lies inside its
epoch, scale within 20 percent of the session's track-extent estimate, runs in `runs.csv` and
`run` labels agree, and finally every selected frame is in exactly one block.

## Non-Functional Requirements

`src/process_lab_data/` in the shape of the converter: `__main__.py`, named values at the top of
each file, one-line docstrings, `pixi run process-lab-data`, `--dry-run`, exit 0, 1 (a session failed a
check) or 2 (setup). pyarrow and numpy only. Tests on small synthetic tables: block cutting at
pauses and gaps, the frame conversion on known points, phase labels on a scripted run.
