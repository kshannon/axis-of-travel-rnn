# axis-of-travel-rnn: rules for coding agents

## Project goal

Two aims, kept apart by their configs. Emergence: does an axis of travel like representation emerge in a vanilla RNN trained only to predict future position, with position as its only input? Here a negative result is a valid outcome, the pipeline is never tuned toward a positive one, and nothing that encodes axis of travel reaches training. Construction: can an RNN be made to produce axis like cells when given the subiculum's inputs, head direction and angular velocity alongside position, and under what constraints? Here tuning toward axis like cells is the point and is done in the open, in the experiment's config. Both aims use the same data, the same windows, the same analysis and the same measures, so the two kinds of network are compared on equal terms. An experiment's config says which aim it serves, and a result is never read against the other aim's rules.

## Long term direction

This is the first study. Later work may look at mechanistic explanations, environmental structure, embodied navigation, world models, biologically inspired AI, robotics, alternative spatial representations and automated experimentation. None of that is built now unless asked for, and nothing here should make it harder later.

## Rules

1. Inputs. The network's inputs are an experiment choice recorded in its config: position only is the control, head
   direction and angular velocity (the block's heading and turn_rate columns) may be added as inputs for a biological
   model of subiculum inputs. Nothing that labels axis of travel ever reaches training: no axis labels, phase, trip, run,
   path, clean, cell type or hand coded travel direction. These stay in the data for validation, controls and post hoc
   analysis. A control experiment that needs one must say so in its config.
1. Data. The data lives outside the repository, which holds no data folder. Raw recordings, transformed frames, review
   json files and block parquet files stay in the folders `configs/local.yaml` names (the reviews in
   `PROCESSED_LAB_DATA/review/`). Only a small synthetic sample (`tests/fixtures/sample/`, no real recording) is
   committed. Never read, move or rename `configs/local.yaml`.
1. Records. Every result names its commit, data id, config and lock hash.
1. Work. Spec, plan and tasks (`docs/<feature>/`) for library changes only. An experiment is a folder and a notebook and
   nothing else. Tests assert invariants only. Run `pixi run test` before claiming anything works. Plain idioms, one
   line docstrings. Flag any choice that could change the scientific interpretation, and report what changed and what
   was verified.
1. Figures. Every figure carries a title, a short caption saying how to read it and what it shows, and which data made
   it (data id or session ids, config, seed). A figure without these is not finished.
1. The lab notebook. `labnotebook/` is the authors' dated log: never write in it, delete or change it unless the authors
   ask and confirm twice. `tmp/` is uncommitted scratch.

## Branches, commits and pushes

- All work happens on a branch created from an up-to-date `main`. Until the restructure lands (`docs/restructure/`) that
  branch is `cleanup`, after it branches are named `agents/<topic>`. Never commit to `main` unless the authors ask.
- A finished branch is a PR candidate. It is never merged, and nothing is pushed to the remote, without the authors'
  consent for that specific action.
- Commits are scoped to the task's files, one sentence commit messages each. No new dependency without the authors' yes.
- Never delete branches, stashes or files outside the task without asking.

## Machine configuration

The authors' own agent configuration (`~/.claude`, `~/.codex`), shell and editor settings and dotfiles are never
changed by project work.

## Map

- `README.md`: the pipeline, quick start, experiments, layout, where the data lives.
- `DATA_DICTIONARY.md`: what every attribute and term means. `docs/blocks_schema.md`: the block step's files and keys.
- `docs/`: specs, plans and tasks per feature (`restructure/`, `transform_lab_data/`), `pilot.md`.
- `configs/project.yaml`: environments, blueprints, EDA defaults, analysis thresholds. `configs/experiments/`: presets.
- `src/axis_of_travel_rnn/`: the library, `config.py` (paths and configs), `blocks/` (the block engine). `src/transform_lab_data/`: the converter.
- `notebooks/eda/` and `notebooks/experiments/` (one folder per experiment). `templates/`: notebooks, lab note, `new.sh`.
- `tests/`: unit, integration (the smoke) and `fixtures/` (the synthetic sample and `make_sample.py`).
- `tmp/`: scratch and planning, never committed.
