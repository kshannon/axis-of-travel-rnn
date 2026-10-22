# Lab data transform plan

Read with spec.md and tables.md. No code: layout, flow, shapes and decisions. The contract of each function is
its one-line docstring.

## Architecture

    src/transform_lab_data/
        __main__.py          command line, setup guards, dry-run text, summary, exit code
        transform_helpers/
            readers.py       file names to sessions, skips, --only, --sample; both MATLAB formats read
            convert.py       table definitions, vocabularies, tag lookup, label scheme; variables to tables
            checks.py        pass, warn or fail on the read variables and on the converted rows
            orchestrator.py  Record (one session through the stages) and Orchestrator (the run, the writes)
            output.py        write_frames, write_csv, write_json
    tests/unit/transform_lab_data/   conftest.py, synthetic_mat.py, test_readers.py, test_main.py, test_convert.py
    pixi.toml (h5py, pyarrow, task transform-lab-data)      pyproject.toml (pytest pythonpath = ["src"])

Each file reads as imports, one block of named values, then functions. Imports flow one way: `readers` and
`output` import nothing of ours, `convert` imports `readers`, `checks` both, `orchestrator` all four, `__main__`
the orchestrator and `readers`. A definition lives in the file that uses it; there is no schema file or class.
The old `lab_data_access.py` helper kept its own reader until the notebooks switch (tasks.md).

## Data flow

`main(argv=None, config=None)` reads `configs/local.yaml` only when `config` is None (tests pass one) and exits 2
on a bad setup. `readers.catalog` finds the sessions and the skipped names, `readers.select` applies `--only`,
then `--sample`. `--dry-run` prints and returns 0 here: no `.mat` opened, nothing written, the output folder not
created. Otherwise `Orchestrator.run` takes each session in recording order and prints one line, then writes
`checks.json`, `manifest.json` and the four CSVs once, in a `finally`. `main` prints the summary and returns 1
when any session failed, else 0.

Per session one `Record` goes through four stages in a loop that stops once the record has failed. Each stage
returns a new record (`dataclasses.replace`); nothing changes in place.

| stage | function | fills |
|---|---|---|
| read | `readers.read` | `trk`, `ana`: the lab's variables by name; a file that does not read raises |
| check inputs | `checks.check_inputs` | `results`: the `provenance` warn, then the three input fails |
| convert | `convert.convert` | `frames`, `rows`, `facts`; pure, no I/O |
| check converted | `checks.check_converted` | `results`: the 15 checks in `checks.CHECKS` |

A record that never failed has its rows validated with `table(name, rows)` and its frames file written at once;
its tables, manifest entry and results stay in memory until the end of the run.

## Shapes

- Frame numbers in tables are the lab's 1-based rows; arrays are indexed `a[frame - 1]` only inside builders.
- `trk` and `ana` are dicts keyed by the lab's variable names, absent ones left out, identical for both formats:
  float64 arrays, the two flag arrays bool, scalars float (None when empty), strings str. A builder copies an
  array before masking it.
- `Record` (frozen, in `orchestrator.py`): `session`, `trk`, `ana`, `frames` (a pyarrow table, NaN never null),
  `rows` (table name to a list of row dicts, None for null), `facts` (tag, stamp status, pauses) and `results`,
  `{check: {status, detail}}`, JSON-ready. Rows stay dicts; `table()` refuses an unknown or missing column, a
  null in a required column or a value outside the four enforced vocabularies.

## Writing and rerun

A frames file is written when its session passes both check stages. Everything else is written once after the
loop: `checks.json`, `manifest.json`, then the epochs, runs, events and sessions CSVs, each the sessions written
this run sorted by key, header-only when there are none. So every run rewrites them whole: a `--only` or
`--sample` run leaves outputs for only its sessions, and frames files of other sessions stay. Nothing is read
back, merged or deleted. Sorted rows and fixed definitions make two runs on the same input identical in CSV,
`checks.json` and Parquet; `manifest.json` differs only in its timestamps. A Ctrl-C still runs the `finally`; an
error in the final writes is not caught.

## Failure policy

`_process` wraps a session's stages, validation and frames write in `except Exception`, recorded as `exception`
with the type and message beside the results so far, so one bad session never stops the others. A file that does
not read, a `sampleRate` or `maxGap` that is not a finite number, a `sampleRate` that rounds to 0 where there are
epochs or runs, and a value `table()` refuses all land there. A fail from either check stage or an exception
means not written, listed under `failed` with its failed checks, exit 1. Expected skips never change the exit code.

## Manifest and checks.json

`manifest.json` describes this run only: `{"sessions": {id: {written_at, provenance, rows}}, "run": {parameters,
only, sample, timestamp, written, failed, skipped, row_counts}}`. `provenance` holds the values the files hold
(null when absent or an empty number), `rows` the row counts per table, `failed` each id with its failed checks.
The lab files are not hashed and the environment is not recorded: the transform runs once. `checks.json` is
`{session_id: {check: {status, detail}}}` for every session processed, written or failed.

## Checks

Fail, so the session is not written: `variables_present` (a required tracking variable missing; `check_inputs`
stops there), `tracking_lengths` (`processedDVT` (N, 10), `HDRadians` (N,), both flags (N, 2), N at least 1),
`frames_contiguous` (frame column 1 to N), `keys_unique`, `rows_conserved` (frames rows equal N; events equal
`spiral_events` row for row, so a non-whole frame or label fails), and `exception`.

Warn, so it is only recorded. Each converted check runs in its own `try/except`; a crash records that check with
the error, a warn (a fail for the two fail checks), so a defective warn check never loses a session.

| check | asks |
|---|---|
| `provenance` | a provenance variable absent or an empty number (not `nRealLights`) |
| `flags_agree` | (1, 1) rows equal the unfilled flags per light; filled and unfilled never both; average light (1, 1) where either is unfilled, mashup where both |
| `heading_nan_matches` | stored heading NaN exactly where either light is unfilled |
| `heading_matches_lights` | heading within 1e-3 rad of atan2(front - back) where both lights are tracked |
| `pauses` | steps in `t` over 0.1 s, listed |
| `stamps_usable`, `tag_known` | stamp status other than ok; a tag missing from the lookup |
| `events_paired` | starts and ends in no pair |
| `events_in_tracking` | event rows at frame 0, below 0 or beyond N |
| `lab_counts_match` | `nRuns` per `pathList` path equals the clean pairs on it; sorted marker pairs equal sorted clean pairs |
| `painted_aligned` | `pixelDvt` has N rows, one more column than `processedDVT`, its first two equal frame and time; else `painted_label` is blank |
| `painted_matches_runs` | each clean run's signed start label is painted within 2 frames of its start and end |
| `rate_matches`, `events_present` | `sampleRate` 60 and `maxGap` 30; `spiral_events` exists (if not, events and runs are empty) |

Not checked, because the tables hold them: overlaps and duplicates (`runs.csv`), event kinds, short epochs
(`duration_s`), runs in the arena (`runs.epoch`), positions outside the frame, the number of lights.

## Decisions

- Builders are pure functions of the read dicts, so the both-formats test carries most of the proof. `pyarrow`
  only, no pandas; the full package, since `pyarrow-core` has no Parquet.
- `timeStamps` are 1-based rows and a segment is the inclusive range (read from `TTAutoPosTracker.m`). One epoch
  per stamp pair: a third pair with no variant tag (none in the 109) is a `variant` epoch in `triple_t`,
  `baseline`, with the `tag` warn (2026-10-11). A count that disagrees with the tag is that warn, and the epochs
  are still made. An infusion or `dark` tag names the whole file; `protocol` comes from the tag lookup, never
  from the epochs.
- `overlap_frames` is the previous run's end minus this run's start plus 1, 0 when not positive: the frames to
  trim from the earlier run, which stage 2's cut rule needs. It equals the shared frames unless this run lies
  inside the previous one. `duplicate_of` compares the signed start label, so a clean run is never a duplicate
  of a dirty one (2026-10-11).
- A pause's length is the step in `t` minus the camera's frame time 1/60 s, not the lab's `sampleRate`. There is
  no fallback for the rate or gap: a value that is not a finite number fails the session.
- `head_dir` is stored as is, with a warn if it is not NaN exactly where a light is unfilled. A misaligned
  `pixelDvt` blanks `painted_label` with a warn. A session without `spiral_events` converts with empty events and
  runs and a warn. Pairing uses only start and end rows.
- Run once (2026-10-11 and 2026-10-12): nothing hashes the lab files or records the environment, code for
  impossible situations was stripped, and a snag is handled by deleting the output and rerunning.
- One `Record` is passed through the stages and the orchestrator alone does the bookkeeping. Six checks were cut
  because the tables already hold what they said.
- The notebooks keep their own reader and catalog copies until the converter is stable, then import from it.

## Tests

The invariants of a run-once converter, on one synthetic session (900 frames, three pauses, three runs, the
lab's sentinels, counts and painted `pixelDvt`) written in both formats, the v7.3 one as MATLAB writes it
(transposed, `MATLAB_class` attributes, cells as references, `MATLAB_empty`):

- `test_convert.py`: both formats read to the values written; positions NaN by the flags, never the pixels;
  epochs and `protocol` by tag; unusable stamps; the pairing rules with the lab's counts, `duplicate_of`,
  `overlap_frames`, `spans_pause`; the rules that fail a session.
- `test_main.py`: the setup guards exit 2; `--dry-run` opens no `.mat` and writes nothing; a failed session does
  not stop the others and exits 1; a rerun gives identical files.
- `test_readers.py`: file names to sessions, skips with reasons, `--only`, `--sample`.

`conftest.py` makes `local_config` raise, so no test reads the real file; every test passes `config`, and tests
patch `main.repo_root`. About 580 lines; 71 tests in the repository suite. Reviewers' mutation tests showed gaps
that were accepted: CSV rows written sorted, `frames_contiguous`, `pixelDvt` frame and time alignment, flags read
as bool, and a crash inside one check.
