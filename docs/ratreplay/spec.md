# RatReplay

A session-level review tool for rat trajectories. It replays one recording session as if live,
draws the blocks the processor would cut, and lets a person confirm, adjust or reject them.
What it saves is the hand review behind the processed dataset (`docs/process_lab_data/`), and
later the test set for a trained network. Written as a package (`src/ratreplay/`) that could
become a standalone tool.

## Out of Scope

- Editing the data: positions are never changed or interpolated, behaviour is never removed,
  run windows are never moved. The tool writes review files, nothing else.
- Labels within a block: `phase` (dwell, return, pause, forage) is a global rule of the
  processor, checked here by eye, never edited per run.
- Statistics, paper figures, synthetic data, anything served beyond localhost or exported
  (AGENTS.md rule 3). Synthetic sessions may be replayed too.

## Overview

`pixi run ratreplay`, a Dash app in the browser at localhost, one session at a time. It reads
the converter's output under `TRANSFORMED_LAB_DATA` (pixels, 60 Hz) and writes one review file
per session under `PROCESSED_LAB_DATA/review/<session_id>.json`. The processor builds exactly
the confirmed blocks of a reviewed session and the automatic ones of an unreviewed session.
The automatic cuts are drawn by the processor's own `cut_at`, so what is confirmed is what is
built. Dependencies `dash` and `plotly`.

## Functional Requirements

### Layout

Two tabs. The Sessions tab is one row per session: rat, date, protocol, duration, automatic
and confirmed block counts, reviewed by, reviewed at and the time since, a notes excerpt, and
a load button that opens the session on the Replay tab. Unreviewed rows first, then the oldest
review first, so the list is the to-do list. A totals line above it: sessions reviewed of all,
blocks confirmed, hours of confirmed block time per epoch kind.

The Replay tab. Top: a session dropdown (unreviewed first, a reviewed mark and the time since
the save), the rat, date and protocol, a "whole session" button, a "reset to automatic" button
(discards the edits in memory, the file stays until the next save), a `?` popover with the
session facts. A line says which state is on screen: automatic, or saved when and by whom with
the number of edits. No command text on the page.
Then the map (occupancy faint, trail of the last 2 s coloured by speed, the current point, the
corrected heading arrow, the raw LED axis and the motion direction are not shown), then
play and pause, the clock (time in session, lab frame), the speed slider 0.25x to 8x. The
occupancy background is drawn per epoch, since the arena, the track and a rotated track
overlap in the camera frame, with a choice: the current epoch only (default), all epochs, or
one epoch by name. A summary line gives the session's numbers: blocks automatic, confirmed,
edited and removed, block time kept of the epoch time, windows at the current knobs, flags.

Below, four lanes on one shared time axis, the hierarchy of a session:

1. `session`: one bar, the arena and track epochs as labelled segments.
2. `runs`: one bar per run, outbound and return in two shades, clean solid and dirty hatched,
   path id and run number on hover only, no legend. A flagged run is outlined.
3. `frames`: the frame-level life: gaps shaded, pauses marked, a thin speed trace, and the
   detectors' flags: a position jump (displacement in one frame above a named threshold) and a
   long one-LED stretch. Flags are what the review looks at.
4. `blocks`: one bar per block with a checkbox, connector lines up to the frames it covers,
   the block id, status colour (auto, confirmed, edited, dropped).

Each block shows how many training windows it yields at the window length and stride set by
two display knobs (defaults 40 s and 10 s, stored nowhere, the training config owns the real
values), and a block shorter than one window is greyed as useless. A selected block shows a
faint ghost of its first windows. Clicking a block zooms every lane and the map's trail to it and shows its facts. The "whole
session" button clears the selection. Clicking anywhere on a lane moves the cursor. Under the
lanes, one line says how the automatic blocks were cut (pauses, both LEDs lost over 0.5 s,
pieces under 10 s dropped) with a `?` popover for the details.

### Actions, the whole range of cleaning allowed

- `confirm`: the checkbox on a block (or `a` to confirm every block).
- `new block`: from the `i` and `o` marks on the cursor. The marks cannot cross a pause, a
  gap or an epoch bound, and the block must be 10 s or longer.
- `remove`: a block (toggle, a removed block stays visible greyed).
- `move`: the start or end of the selected block to the cursor (`,` and `.`), snapping to a
  run start or end within 1 s and never crossing a pause, gap or epoch bound.
- `split`: the selected block at the cursor (`s`).
- `flag`: a run as mislabelled (`f` on the runs lane), its labels are cleared by the processor,
  the frames stay.
- `note`: free text on the session.
- `save session`: writes the review file for this session, overwriting the earlier one, so a
  session can be changed and saved again (idempotent). Refused while any block is still auto.
  Then the next unreviewed session opens.

### The review file

`PROCESSED_LAB_DATA/review/<session_id>.json`: `session_id`, `reviewed_by`, `reviewed_at`,
`converter_manifest_timestamp`, `blocks` (each: `block_id`, `epoch`, `environment`,
`frame_start`, `frame_end`, `status`, `note`), `cuts` (each: `frame_start`, `frame_end`,
`reason`), `flagged_runs` (run numbers), `notes`. Saving again overwrites the file for that
session. Human readable, one file per session.

### Playback and keys

The session's arrays are sent to the browser once. Playback runs in the browser on the wall
clock, so 1x is real time. Keys: space play and pause, left and right one frame, shift with
them one second, `[` and `]` previous and next run, `{` and `}` previous and next block, Enter
confirm the selected block, `a` confirm all, `i` and `o` mark a range, `n` new block from the
marks, `d` remove or restore the block, `,` and `.` move the selected block's start or end to
the cursor, `s` split at the cursor, `f` flag the run under the cursor (or a right click on its
bar), `z` undo, Escape back to the whole session. Buttons exist for confirm all, new block from
marks, start and end to cursor, split, remove, undo and save. Confirming one block is a click on
its glyph or Enter. The review file records the rule constants it was saved under, and edits
that no longer apply after a rule change are skipped and counted on screen.

### Checks

Exit 2 when a data folder or its manifest is missing. A session that fails to load shows the
error in the title. The timeline's cuts equal `process_lab_data.select.cut_at` on the same
frames, tested.

## Non-Functional Requirements

`src/ratreplay/`: `data.py` (loading a session, the review file), `app.py` (layout and
callbacks), `assets/replay.js` (playback, keys, drawing). Named values at the top, one-line
docstrings, no state outside the browser and the review file. Every figure has a title and a
caption saying how to read it and which session it shows. Tests on a synthetic session:
loading, the review file round trip, the timeline cuts against `cut_at`, the edit operations
on the block list (move with snapping, split, drop, cut).
