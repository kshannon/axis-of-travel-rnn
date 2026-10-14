# Process lab data tasks

One commit per task on `agents/clean-runs`, verified by `pixi run test` plus the listed command.
Kyle runs everything that touches the data.

- [x] T1 Spec and plan under `docs/process_lab_data/`, the `PROCESSED_LAB_DATA` key in
  `configs/local.example.yaml`. [all]
- [ ] T2 Skeleton and funnel: `src/process_lab_data/` with `__main__.py` and `select.py`, the task
  `process-lab-data`, the setup guards (both keys, folders, not inside the repository), the funnel
  over the four tables printing the count after each step, and `--dry-run`. Test: the funnel on a
  small synthetic set of tables. Verify: `pixi run process-lab-data --dry-run` (Kyle) prints the
  counts of sessions, epochs and blocks. [Selection]
- [ ] T3 Block cutting: pauses, gaps, epoch bounds, the minimum length, applied to the frames of
  one session. Test: a scripted frames table with one pause and one gap gives the expected
  blocks. Verify: the dry run reports blocks per epoch. [Overview, Selection]
- [ ] T4 Frame conversion: LED scale per session and epoch, flip, heading conversion, track
  rotation and translation, the parameters in the manifest. Test: known points round trip.
  Verify (Kyle, notebook): scale against the track extent, heading sense on a known turn, the
  start site after translation. [Frame conversion]
- [ ] T5 Kinematics and labels: the versioned derivation of speed and turn rate in
  `axis_of_travel_rnn/trajectory.py`, the run, path_id, clean and phase labels. Test: a scripted
  run gets the expected phases, the derivation on a known path. [Phase labels]
- [ ] T6 Writers and checks: block parquet files, the two blocks csv files, `manifest.json`, the
  checks, exit codes, the summary. Test: a synthetic session end to end writes what the spec
  lists and a rerun is identical. Verify: `pixi run process-lab-data` (Kyle), full run. [Outputs,
  Checks]
- [ ] T7 Loader: `trajectory.py` reads a block back into the schema, with a test on a written
  block. README usage lines. [Non-Functional]
