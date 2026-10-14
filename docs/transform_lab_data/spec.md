# Lab data transform

Converts the lab's MATLAB files for each recording session into CSV tables and one Parquet file
of frames per session, so the data can be used without MATLAB. Stage 1 of three, and a
conversion only: it keeps the lab's values and variables, drops no rows, edits no values and
adds only labels and flags. Cleaning, subsetting and every choice with a scientific
interpretation belong to stage 2 (cleaning, room-frame trajectories) and stage 3 (statistics),
which get their own specs.

## Overview

A session is one tracking file (`...ProcessedDVT.mat`: two head LEDs at 60 Hz, a heading, flags
for lost, filled and unfilled samples) and one analysis file (`..._rmaps.mat`, with `tt` and a
variant tag in either order: epoch timestamps and the lab's manual run labels). The converter
reads every session it can and writes, under the transformed lab data root, `sessions.csv`,
`epochs.csv`, `runs.csv`, `events.csv`, `manifest.json`, `checks.json` and one
`frames/<session_id>.parquet` per session. `annotations.csv` is written by hand, never by the
converter. `session_id` is on every row, conditions are labels (the baseline set is a filter,
not a loader branch), and the lab's segmentation and labels are copied, never invented.

It is the package `src/transform_lab_data/`, run with `pixi run transform-lab-data`, not part of the
CLI. `LAB_DATA` and `TRANSFORMED_LAB_DATA` come from `configs/local.yaml`, never from arguments.
Columns and the quirks of the lab's files are in `tables.md`, plain-English terms in
`DATA_DICTIONARY.md`, the structure, checks and decisions in `plan.md`.

## Functional Requirements

### Inputs

- Subject folders (`NS14Data`, `JL1HPCData`; the folder is the group) of `.mat` files named
  `<subject>_rec<N>_<MMDDYY><sss>[_tags]<kind>.mat`. Tags are matched without regard to case.
- A session is exactly one tracking file and one analysis file with the same subject, recording,
  date and session digits (always one to one in the 109 found). Names that don't parse
  (`allPLXFiles.mat`, a malformed twin) and sessions missing or doubling a file are listed in the
  manifest as skipped, with the reason. Never fatal.
- Both MATLAB formats: classic through scipy, v7.3 through h5py. Only the variables the converter
  uses are read, plus a few provenance values for the manifest; neural arrays never are. A file
  that cannot be read fails its session and the run goes on.

### Running the converter

`pixi run transform-lab-data`, three optional flags that combine:

- `--dry-run`: prints the sessions it would convert, the skipped names with reasons, counts per
  group and the files it would write. Opens no `.mat` file, writes nothing.
- `--only PREFIX`: sessions whose id equals PREFIX or continues it after an underscore: a subject
  (`NS14`), a recording (`NS14_rec10`; `NS14_rec1` does not take `NS14_rec10`) or one id.
- `--sample N`: the first N sessions per subject in recording order, after `--only`.

One line per session as it finishes, then a summary. Exit 0 when every selected session was
written, 1 when any failed or could not be read (expected skips do not count), 2 for a bad flag
or a setup problem: a key missing from the config, the lab folder not a folder, or the output
equal to, inside or containing the lab data, or equal to or inside the repository.

Run once: every run rewrites the four CSV tables, `manifest.json` and `checks.json` whole, from
the sessions it processed, so a `--only` or `--sample` run leaves tables for only its sessions;
frames files from earlier runs stay untouched. The same input twice gives identical CSV,
`checks.json` and frames bytes. Nothing is merged, repaired or deleted: to start clean, delete
the output folder and rerun. The converter writes only under `TRANSFORMED_LAB_DATA`.

### Outputs

The files named in the Overview, one row per recording (`sessions.csv`), epoch, run, event or
60 Hz frame. Columns are in tables.md 2.1 to 2.7, vocabularies in 2.8. `condition` is free text,
so an unknown tag is kept verbatim on the variant epoch and reported.

### Behavior

- Faithful: no resampling, coordinate change, smoothing or dropped rows. Pixels stay pixels, both
  lights are kept, the lab's heading and `t` as stored. A light's (1, 1) sentinel becomes NaN,
  decided by the unfilled flags and never the pixel value (the lab's average light: either light
  unfilled; its mashup light: both); the flags stay as columns; values outside 640 by 480 are
  kept.
- Time: `t` is frame times 1/60 s only while the camera runs; in 32 of 109 files the recording
  paused and `t` jumps by minutes. Frames stay contiguous and authoritative, and the lab's event
  times follow `t`, so they look shifted after a pause. A pause is a step in `t` over 0.1 s, its
  length the step minus 1/60 s, counted in `sessions.csv` and listed in `checks.json`. Durations
  are frames divided by the lab's rounded `sampleRate`; one that is not a finite number fails the
  session.
- Epochs come from `timeStamps`: segment 1 is `arena`, 2 `track`, 3 `variant` (6 entries; in the
  lab's files exactly when the name carries a variant tag). Every pair is kept, even under 10 s.
  Environment and condition come from the tag lookup (2.8); an infusion or `dark` tag puts every
  epoch under that condition. Stamps that are not 4 or 6 whole, increasing numbers inside the
  tracking give no epochs and a warn. No fallback.
- Events: `spiral_events` goes to `events.csv` as stored, in click order, with a `kind` from its
  label.
- Runs, by pairing only. Only start and end events take part. In click order, a start is paired
  with the next start or end event only when that event is its end (label plus 100, same sign);
  otherwise that start stays unpaired and the next event is considered on its own. An event in no
  pair has a blank `run` and a warn. Runs are numbered by start frame; `clean` is the sign of the
  start label. Flags, never edits: `duplicate_of`, `overlap_frames` and `spans_pause` (tables.md
  2.3). A run's epoch holds its start frame.
- A frame's `epoch` is the epoch whose range holds it, blank elsewhere. `painted_label` is the
  lab's per-frame run label (the last column of `pixelDvt`), blank, with a warn, when it is absent
  or does not line up with the tracking.
- `sessions.csv` holds file facts and counts, no derived scientific value.

### Checks

Every session is checked before it is written; results go to `checks.json` as pass, warn or
fail. A `fail` means the session cannot be converted faithfully: a required tracking variable
missing, tracking arrays of the wrong shape or no frames, frame numbers not 1 to N, a duplicate
key, converted rows that differ from the lab's, or an error while reading, converting or writing.
It is not written, is listed in the manifest and `checks.json` with the reason, and never stops
the run. Everything else the lab's data can show is a `warn` and the session is written. What the
tables already show (overlaps, duplicates, short epochs, runs in the arena, positions outside the
frame) is not checked; stage 2 filters on those columns. The lists are in `plan.md`.

## Non-Functional Requirements

- Dependencies: `h5py` and the full `pyarrow` (Parquet and CSV); no pandas.
- Tests use small synthetic `.mat` files in both formats and cover the run-once invariants listed
  in `plan.md`. No real data in the repository, ever.
- AGENTS.md rule 3 is reworded in its own pull request: the recordings and the per-frame, per-run
  and per-event tables made from them never enter the repository, the artifact store or the CLI;
  the code that converts them lives in `src/transform_lab_data/` and reads and writes outside the
  repository; only aggregate statistics files reach the tool.

## Out of Scope

- Stage 2: dropping or cutting runs and short epochs, epochs for sessions without stamps,
  `hd_offset_rad`, `run` and `phase` labels on frames, pixel scale, registration, resampling,
  reading `masterTemplate` and `PathTemplate` (rules validated by hand: tables.md 3.1).
- Stage 3: statistics and the reference file.
- Neural data; our own run or epoch detector; spot-check figures (the lab-data notebooks do
  that); analysis of infusion and dark sessions (converted, then filtered out); route and goal
  names, until the path mapping is known.
