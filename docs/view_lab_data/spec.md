# View lab data

A local review tool for the lab trajectories: play a block or a run as if live, read its labels,
and save a tag and a comment per run. The verdicts it writes are the hand review behind the
processed dataset (`docs/process_lab_data/`) and, later, the synthetic dataset.

## Out of Scope

- Editing the data. The viewer reads and only ever appends to `verdicts.csv`.
- Statistics, figures for papers, synthetic data. The viewer shows one block at a time.
- Anything served beyond localhost, and any artifact or export of the real data (AGENTS.md
  rule 3). Synthetic blocks may be viewed too, but sharing views is a later tool.
- Phase detection and registration: the viewer shows the labels the processed data carries.

## Overview

One Dash app, `pixi run view-lab-data`, opened in the browser at localhost. It reads either the
processed blocks under `PROCESSED_LAB_DATA` (metres, labels, the normal case) or, with
`--transformed`, the converter's frames under `TRANSFORMED_LAB_DATA` (pixels, runs from
`runs.csv`), so real runs can be looked at before the processed dataset exists. Dependencies
`dash` and `plotly`, approved by the author on 2026-10-13.

## Functional Requirements

### Layout

Left panel: dropdowns for session, block and run, then the labels of what is on screen
(subject, date, group, epoch, duration, path_id, clean, phase, speed), then a tag dropdown
(fine, tracking artifact, run mislabelled, unsure), a comment box and a save button. Main panel: the figure, with a title
naming the session, block and run, the block's occupancy as a faint background, the trail of
the last 2 s coloured by speed, drawn large enough to read, the current point and a heading
arrow (corrected by the session's LED offset, with a toggle for the raw LED axis and the motion
direction), and the start and goal
sites from the environment config once the data is registered. Under it the play and pause
button, the timeline slider with the time in seconds and the lab frame number, a strip showing
the run windows along the block coloured by path id with the returns between them, the speed
slider (0.25x to 8x) and previous and next run buttons. Bottom: a table of every block and run
in the dataset with duration, n runs, the latest tag and comment, click a row to load it.

### Playback

A block's arrays are sent to the browser once as JSON. Playback runs in the browser on an
interval, at the native rate or 20 Hz when the browser is slow, scheduled on the wall clock so
1x is real time. The timeline scrubs anywhere. On load the viewer opens the first run without a
verdict and starts playing. Keys: space play and pause, left and right one frame, shift with
them one second, `[` and `]` previous and next run, `f` `t` `m` `u` tag fine, tracking artifact,
run mislabelled, unsure.

### Verdicts

A verdict marks a tracking or labelling problem, never a behaviour: a rat that slows, stops or
scans is data to keep and the phase labels say what it did. `verdicts.csv` beside the data (under `PROCESSED_LAB_DATA`, or `TRANSFORMED_LAB_DATA` with
`--transformed`), one row appended per save: `block_id`, `session_id`, `run`, `tag`, `comment`,
`saved_at`, `who` (the login name), `dataset_manifest_timestamp`. Never edited in place. The
table shows the latest row per run. A run with no row is unreviewed.

### Checks

The app refuses to start (exit 2) when the data folder or its manifest is missing. A block that
fails to load shows the error in the figure title instead of crashing the app.

## Non-Functional Requirements

`src/view_lab_data/`: `app.py` (layout and callbacks), `data.py` (loading blocks and runs from
either source, the verdicts file). Named values at the top, one-line docstrings, no state
outside the browser except the verdicts file. Tests: `data.py` on a small synthetic block
(loading, the latest verdict per run, appending a row). The app itself is checked by hand.
