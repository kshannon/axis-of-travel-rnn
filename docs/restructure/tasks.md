# Restructure tasks: from the repository as it is to Plan A

Read with `restructure-plans.md` at the root and https://goodresearch.dev. Branch `cleanup`, cut from
`main` on 2026-10-21. One commit per step, each verified by `pixi run test` plus the listed check.
Estimates are agent time. Kyle runs anything that touches real data. RatReplay keeps running from
branch `agents/synthetic` while Kyle cuts blocks, so the cleanup work happens in a git worktree of
`cleanup` until he is done, and nothing here deletes `ratreplay/` before his copy is confirmed.

State at the start: `main` and the deleted `feature/basic-RNN-pipeline` were identical. The untracked
work (src/lab_rnn, the 2026-10-19 lab-rnn notebook, the 2026-10-20 run durations notebook) is
stash@{0} of 2026-10-21. The pilot code is in tmp/pilot, git ignored, on disk.

## The steps

- [x] 1. Worktree and stash: `git worktree add ../axis-of-travel-rnn-cleanup cleanup`, pop the stash
      there, commit src/lab_rnn and the two notebooks (outputs stripped), move `restructure-plans.md`
      to `docs/restructure/plan.md`. Check: `git status` clean. (1 h)
- [x] 2. Kyle: confirm the RatReplay copy in its own repository (branch `agents/synthetic` at 4b22a06 or
      later), rename the GitHub repository to axis-of-travel-rnn, `git remote set-url origin`. (Kyle)
- [x] 3. Remove RatReplay here: `ratreplay/`, its pixi feature, environment and tasks, its pyproject
      entries. Check: `pixi run test` green, `git grep -i ratreplay` names only docs. (1 h)
- [x] 4. Remove the CLI, the artifact store, `__main__.py`, `lab_data_access.py` and their tests, keep
      `paths.py`, `notebooks.py` and the two notebook tasks. Check: `pixi run new-jupyter-nb --help`. (1 h)
- [x] 5. Dependencies: drop fastapi, uvicorn, nodejs, pymc, arviz, nutpie, pynwb, dandi, zarr, xarray,
      ratinabox, einops, pynapple, add tqdm and pandas, lock regenerated. Check: tests green,
      `pixi run python -c "import torch, pyarrow, scipy, matplotlib, pandas, tqdm"`. (1 h)
- [x] 6. Docs and configs: delete `docs/cli`, `docs/notebooks`, `docs/process_lab_data`,
      `docs/ratreplay`, the plus maze and rotated environment yamls, strip RatReplay wording from
      `trajectory.py`, `windows.py` and `triple_t.yaml`. Keep `docs/transform_lab_data`. Check:
      `git grep -i ratreplay` empty outside docs/restructure. (1 h)
- [x] 7. Notebooks to the top level: `notebooks/eda/` for the four October EDA notebooks, `notebooks/`
      for the rest, the template and `new-jupyter-nb` follow, nbstripout stays. (30 min)
- [x] 8. AGENTS.md and the rule on data: the pipeline is transform, build blocks, experiment. Raw
      recordings, transformed frames and block parquet never enter the repository, the review json
      files and a synthetic sample do. Check: Kyle reads it. (30 min)
- [x] 9. The block engine back in: `src/axis_of_travel_rnn/blocks/` from
      `git show agents/synthetic:ratreplay/backend/ratreplay_api/engines/trajectory/*` (cuts, heading,
      frame, room, kinematics, labels, session, edits, build, funnel, windows), RULES as the defaults,
      the engine's unit tests and frozen record with it. Check: tests green with the new count. (3 h)
- [x] 10. The reader and writer: `blocks/io.py` from RatReplay's transformed reader and processed
      writer (blocks.csv, block parquet, metadata json, written whole). Check: unit tests over a temp
      folder. (2 h)
- [x] 11. The blueprint and the build: `configs/blueprints/blocks_v1.yaml` (name, format version,
      sessions, rule overrides, start offsets, review folder, expected data id), `data/reviews/` for the
      review json files, `pixi run build-blocks --blueprint blocks_v1` writing
      `PROCESSED_LAB_DATA/blocks_v1/` with `manifest.json` (data id, blueprint hash, transformed stamp,
      commit, built at). A session without a review is listed and skipped. Check: two fixture sessions
      build with a stable id. (3 h)
- [ ] 12. Kyle: run `build-blocks`, which reads the review files where RatReplay writes them
      (`PROCESSED_LAB_DATA/review/`, no copy step since 2026-10-22), and compare with RatReplay's blocks
      (`diff -rq` or the parity script). A difference is a finding first. Write the data id into the
      blueprint. (Kyle, 1 h)
      The commands, with P the PROCESSED_LAB_DATA folder: `pixi run build-blocks --blueprint blocks_v1`, then
      `pixi run python scripts/compare_blocks.py "$P" "$P/blocks_v1"`, which compares every block parquet and blocks.csv
      by content (the two lock files carry different pyarrow versions, so `diff -rq "$P/blocks" "$P/blocks_v1/blocks"`
      may differ in file bytes alone) and exits 1 on a difference. The metadata json files differ in code_version and
      built_at by design. On the fixtures the parquet files and blocks.csv came out byte identical to the review tool's.
- [x] 13. `docs/data_dictionary.md`, one page: the three folders, the block columns with units,
      blocks.csv, metadata, the blueprint keys, the data id, what stays out of training. It replaces
      the old dictionary and `outgoing_data_schema.txt`. (1 h)
- [x] 14a. The pilot work back on disk: restore the pilot package from branch `feature/pilot` into a
      `pilot/` folder at the root, untouched (tmp/pilot left the disk on 2026-10-21, Kyle keeps the
      pilot as a separate folder to deal with later). Git ignores nothing there, it is committed as it
      was, with a README line saying it is the October pilot and not imported by the library. (30 min)
- [x] 14. The training library, lifted from `pilot/` into `src/axis_of_travel_rnn/` as copies that
      leave `pilot/` as it is: `models.py`, `dataset.py` (scaler, windows to tensors, leakage check),
      `train.py` (Trainer, predict, window_sse, the persistence baseline, hidden_states), `analysis.py`
      (axis measures, segments from phase, path_id and the triple_t geometry), `viz.py` (loss curves,
      rate maps, heading tuning, cell heatmap, PCA, every figure with title, caption and data id),
      `data.py` from `lab_rnn/blocks.py` (split by date, read only guard). Not lifted: worlds, sweep,
      decision, study. `src/lab_rnn` deleted. Tests: shapes, no leakage, the measures on a hand made
      hidden state. (4 h)
- [x] 15. Config and surface: `ExperimentConfig` as pydantic from yaml (data, windows, model, training,
      analysis, seed), `configs/experiments/baseline.yaml`, `configs/analysis/thresholds.yaml`, every
      library function taking the config or its fields, the public surface in `__init__.py`
      (load_blocks, make_windows, make_dataset, train, evaluate, measures, figures, save_results),
      version 0.2.0 and `CHANGELOG.md`. Check: `help(axis_of_travel_rnn)` lists them. (2 h)
- [x] 16. Experiments as folders: `templates/experiment/` (config.yaml, notebook with a parameters
      cell, README with purpose, notes, outcome), `pixi run new-experiment "<title>"` making
      `experiments/YYYY-MM-DD_<slug>/`, `save_results` writing `summary.json` (commit, version,
      blueprint and data id, resolved config, pixi.lock sha256, timings, metrics), `metrics.csv`,
      `figures/` and an html export of the executed notebook. Check: a test over a temp folder. (3 h)
- [ ] 17. The baseline experiment reproducing the 2026-10-19 notebook on blocks_v1, run by Kyle,
      outputs committed under 5 MB, `docs/experiments.md` index with its row. (Kyle 1 h, agent 1 h)
- [x] 18. The drift guard: `data/sample/` from a RatReplay synthetic set (three blocks, about 2 MB,
      no real recording) with its own blueprint and `configs/experiments/smoke.yaml`, `pixi run smoke`
      running the template notebook headless with papermill in under a minute, wrapped in a test.
      papermill as a dev dependency. (2 h)
- [x] 19. README to one page (the question, the three steps, quick start, starting an experiment,
      layout, where data lives, how to get blocks_v1) and a documented `rclone` line for sharing the
      blocks with a sha256 manifest check. (1 h)
- [x] 20. Debrief appended to `docs/restructure/plan.md`: what moved, what was dropped, the parity
      result, the Plan B hooks (`dvc add` on `processed/<blueprint>`, build-blocks as its one stage,
      Quarto over the experiment notebooks). (30 min)

About four and a half days of agent time plus Kyle's three steps. Steps 1 to 8 are the cleanup, 9 to
13 the data step, 14 to 18 the experiment pipeline, 19 and 20 the wrap up. Nothing blocks Plan B
later: the data id and the experiment folders are what it would build on.

## After the cleanup, first in line

Three EDA notebooks Kyle named on 2026-10-21 as very important, each under `notebooks/eda/`, reading
the blocks through the library, each figure with its title, caption and data id, scoped with Kyle
before it starts:

- [ ] E1 Block creation and the issues seen in blocks: a catalogue of what looks wrong in the blocks_v1
      blocks (short tracking losses, jumps, margins, heading gaps, trips that cross cuts), each with a
      count, an example figure and the rule or check that would catch it, feeding the blueprint.
- [ ] E2 Angular velocity: its derivation from the heading, its distribution by phase and speed, its
      noise, and what the smoothing does to it.
- [ ] E3 Head direction and its interpolation: where heading is lost, filled and held, how the fills
      compare with the measured heading around them, and whether the fill limit is right.
