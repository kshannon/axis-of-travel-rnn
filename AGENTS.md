# axis-of-travel-rnn: instructions for coding agents

Project rules for Agent interaction are here, as well as brief context on the project. The bottom is a mapping to help describe where to find information based on goals.

## Project Goal

Does an axis-of-travel-like representation emerge in a vanilla RNN trained only to predict future position? A negative result is a valid outcome. Never optimize the pipeline toward a positive one. We are seeking to observe emergent properties within the RNN's latent space. This is based on work by Olsen et al. 2017. The paper that observed axis-of-travel tuning in subiculum neurons.

## The pipeline

Three steps, each a function of its inputs (`docs/restructure/plan.md`).

1. Transform: the lab's MATLAB files become plain tables (`pixi run transform-lab-data`).
1. Build blocks: the transformed tables, the review files (the person's cuts and flags per session) and a blueprint
   yaml become the blocks, `pixi run build-blocks --blueprint <name>`.
1. Experiment: an experiment folder, a config and a notebook, turns the blocks into windows, a trained network,
   measures and figures.

This is the target. Steps 9 to 18 of `docs/restructure/tasks.md` bring steps 2 and 3 into the repository, until then
the review tool and the training code live outside it.

## Important Contextual Considerations When Working

1. Nothing that encodes axis of travel reaches RNN training: no axis labels,
   head direction, angular velocity, hand-coded travel direction, cell-type or
   cell-class labels. These stay in the data for validation, controls and
   post-hoc analysis. A control experiment that needs one must say so in its
   config.
1. Behavioral generation is validated on its own, against real behavior,
   before it feeds training. The model never shapes how behavior is generated.
1. Raw recordings, transformed frames and block parquet files never enter the
   repository. They stay in the folders `configs/local.yaml` names. The review
   json files (`data/reviews/`) and a small synthetic sample (`data/sample/`,
   no real recording) do.
1. Every trained network is a model animal with a manifest: seed, configs,
   dataset, environment hash, commit, lockfile, checkpoints, metrics. Failures
   are kept. Seeds are never cherry-picked.
1. Artifacts are write-once, addressed by id and content hash, never modified
   in place. Explicit seeds and explicit RNGs, no global state.
1. Small code commits and simple code. Research code should be done via spec-driven design. No new dependencies without a
  reason validated by the authors.

## How work happens

- Spec-driven, one step at a time: `docs/<feature>/spec.md` (about 80-120 lines,
  out-of-scope written first) and validated by the authors before any other work is performed. Then `plan.md` (no code) is created to enure we are in agreement, and finally `tasks.md` (atomic, verifiable) which are mostly at the commit level so we can see the plan as it will be done in action. Implement one task at a time, tests with it as well, but only necessary tests, simplify the code and approach, and as a frontier model, you keep the state and goals, but have models, e.g. opus and sonnet, write the code and offer design choices that are simple, but you and the authors should be approving the design/architecture.
- `docs/` is light and committed: specs, plans, tasks, the data dictionary, reproduction steps. `tmp/` is uncommitted scratch for planning and working notes. `labnotebook/` is the author's dated log, i.e. do not write in it, delete, or modify its contents at all. Unless the authors ask and you receive double confirmation.
- Tests assert critical scientific and structural invariants, not exhaustive
  coverage, and never what a library already guarantees. Run `pixi run test`
  before claiming anything works.
- Standard idioms over cleverness. A docstring is one line of text on its own
  line between the quotes. A stub is a name, a help line and exit 3 until it
  is implemented; its arguments arrive with the implementation.
- Subagents may draft code or proposals. The session that dispatched them
  reviews the diff and runs the tests before anything is committed.
- Flag any choice that could change the scientific interpretation. Report
  exactly what changed and what was verified.
- Every figure carries a title, a short caption saying how to read it and what
  it shows, and which data made it (dataset or session ids, preset, seed). A
  figure without these is not finished, in notebooks, scripts and reports alike.

## Branches, commits and pushes

- All work happens on a branch created from an up-to-date `main`. Until the
  restructure lands (`docs/restructure/`) that branch is `cleanup`, after it
  branches are named `agents/<topic>`. Never commit to `main` unless the
  authors ask for that commit.
- A finished branch is a PR candidate. It is never merged, and nothing is
  pushed to the remote, without the author's consent for that specific action.
- Commits are scoped to the task's files, one sentence commit messages each.
- Never delete branches, stashes or files outside the task without asking.

## Machine configuration

Author's own agent configuration (`~/.claude`, `~/.codex`), shell and editor
settings and dotfiles are never changed by project work.

## Map

- `README.md`: what this is, how to run it, versioning layers, layout.
- `docs/restructure/`: the plan and the twenty steps from the repository as it
  was to the pipeline above. `docs/transform_lab_data/`: the lab data
  converter's spec, plan and tasks. `docs/data_dictionary.md`: the review,
  block and manifest files of the block step, columns, keys and the data id.
- `configs/`: declarative YAML. `environments/` today, `blueprints/` and
  `experiments/` as they land. `configs/local.yaml` is the one machine-local
  file: paths only, git-ignored, never hashed.
- `src/axis_of_travel_rnn/`: the block schema, kinematics, reader and window
  rules today, then `blocks/` (the block builder), models, dataset, training
  and analysis as they land. `src/environments/`: environment geometry.
- `src/proj_helpers/`: paths, new notebooks and lab notes.
- `src/transform_lab_data/`: the lab data converter.
- `src/lab_rnn/`: the adapter that trained the pilot networks on reviewed
  blocks, replaced in step 14.
- `data/`: `reviews/` (the review json files) and `sample/` (the synthetic
  sample), both committed, as they land. The real data is outside the repository.
- `experiments/`: one folder per experiment with its config, notebook and
  results, as they land.
- `notebooks/`: the working notebooks, `notebooks/eda/` for the exploratory
  ones. `templates/`: the notebook and lab note templates.
- `datasets/`: datasets on disk, git-ignored.
- `tmp/planning/`: the full project overview and working notes, never committed.
