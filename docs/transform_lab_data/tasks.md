# Lab data transform tasks

The converter is built; this list records how and what is left. It was written in commit 144bf74 and moved
under `src/` in 8adb139. Spec sections in brackets.

## Validate by hand (done)

Findings are in tables.md 1.4. Nothing was committed.

- [x] V1 Catalog the lab data root from names: 109 tracking and 109 analysis files, one to one; 2 names skipped
  (`allPLXFiles.mat`, a malformed twin). [Inputs]
- [x] V2 Frames in the first session of each group, both formats: sentinels to NaN from the unfilled flags,
  heading and flags hold; positions outside the frame are the lab's interpolation, kept as stored. [Behavior]
- [x] V3 Epochs from `timeStamps`: authoritative (103 of 103 valid); segment 3 exists exactly with a variant tag;
  the tag lookup. A fallback from tracking gaps belongs to stage 2. [Behavior]
- [x] V4 Runs from `spiral_events`: markers and `nRuns` hold clean runs only; rows are authoritative; 32 files
  pause; click order; row-0 placeholders, unmatched starts, duplicates, boundary overlaps. [Behavior, Checks]
- [x] V5 `hd_offset_rad` about 105 degrees, stable across floors and epochs; moved to stage 2. [Out of Scope]

## Build (done)

- [x] S1 Dependencies and config: full `pyarrow`, `h5py`, the task `transform-lab-data`, pytest `pythonpath`
  (commit 0bb0250). [Non-Functional]
- [x] S2 to S10 The package and its tests: `readers`, `convert`, `checks`, `output`, `orchestrator`, `__main__`,
  and the synthetic session in both MATLAB formats. Verify: `pixi run test`; `pixi run transform-lab-data --dry-run`.
  [Inputs, Running, Behavior, Checks]
- [x] R1 to R6 Reworked on 2026-10-11 and 2026-10-12 from a `schema.yaml` and a pipeline into one `Record` passed
  through the stages, plain definitions in the files that use them, a plain writer and a smaller test suite. The
  reasons are in plan.md Decisions. [Non-Functional]
- [x] S11 Docs: the README section "Converting the lab data"; the reproduction steps moved into the README.
  [Non-Functional]
- [x] S12 First real run, by the author: 109 sessions written, 0 failed, 2 skipped. `painted_matches_runs` warns
  in 7 NS14 sessions, where about half the clean runs differ at start and end: a labeling difference in the lab's
  painted column, not a converter fault. [Checks]

## Left

- [ ] S12b Second real run into a fresh output folder, then `diff -rq` against the first: only `manifest.json`
  timestamps should differ. By the author, commits nothing. [Running]
- [ ] Rule 3 AGENTS.md reword, in its own pull request (spec Non-Functional).
- [ ] S13 Once S12b is clean: the lab-data notebooks and the old `lab_data_access.py` helper import `load_mat`
  and the catalog from `transform_lab_data` instead of their own copies. Commit: "Import the lab data reader and
  catalog from the converter package in the notebooks". [Non-Functional]
