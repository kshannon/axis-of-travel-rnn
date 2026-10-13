# axis-of-travel-rnn CLI

PR 1, branch `feature/cli`: the package layout, the store, real `store`, `env` and
list commands, and bare stubs for everything else. Later PRs implement one group at a
time under their own spec, plan and tasks.

## Overview

One command, `axis-of-travel-rnn`, orchestrates the pipeline: environments, behavioral agents,
datasets, models, analysis, experiments. It is a thin layer over this package with no science
capabilities of its own. Every command that produces data writes a registered artifact with a
manifest into a store, and the CLI is the only path that writes artifacts. Helpers that write
nothing stay in `src/proj_helpers/`.

An artifact is the recorded product of one pipeline step: a dataset of synthetic trajectories, a
trained model (one model animal), or an experiment (a population of models trained under one
config). Each is a directory under `<store>/<kind>/<id>/` whose `manifest.yaml` is its receipt:
what produced it (config names and hashes, seeds, upstream artifact ids and hashes), the code
state at the time (git commit, lockfile hash, package and component versions), and what came out
(status, metrics, locations of checkpoints or reports). Artifacts are outputs; configs are inputs.
Environments and agents are configs with content hashes, committed to git. Artifacts live in a
store outside git, on this machine or an external drive, because the manifest makes them
regenerable from configs, code and seeds. They form a lineage, dataset to model to experiment,
and smaller products such as hidden-state recordings, evaluations and axis results attach inside
the model they came from rather than becoming kinds of their own. Two rules follow: an artifact
is never modified or overwritten, so any change is a new id; and the same inputs, identified by
their hash, yield the same artifact, so writers reuse before they create.

## Functional Requirements

### Commands

One group per layer. `<x>` is required, `--x` optional. Purpose says what it does; rationale
says why it exists. Arguments shown for unimplemented commands are the planned shape; they are
defined in code only when the command is implemented.

| command | purpose | rationale |
|---|---|---|
| `store init [DIR]` | create the store layout and its `store.yaml` marker at DIR, default the resolved store | writers only write into a marked store, which catches an unmounted drive or a mistyped path |
| `store inspect [--json]` | resolved path and how it was resolved, marker contents, counts per kind | the first command of the day: confirm where work will land before any of it happens |
| `env list` | every environment config with type, walls, routes, hash | the hash is what every dataset records; see it before anything runs |
| `env inspect <env> [--json]` | geometry summary, or the canonical spec as JSON | what is printed is exactly what is hashed, so configs can be diffed |
| `agent list` | every behavioral profile with hash, headline stats, and how many datasets, models and experiments use it | agents are the unit of behavioral variation; know how much rests on each |
| `agent inspect <agent> [--json]` | parameters, current and superseded hashes, and everything referencing each | trace a behavioral assumption to every result it touched |
| `data list` | registered datasets with environment, agents, input hash, created | the store is the database; listing finds the id to pass onward |
| `data inspect <dataset> [--json]` | manifest, session and trial counts, split, validation status | confirm contents and validation before training on it |
| `data generate --config <yaml> [--seed N] [--dry-run]` | build a synthetic dataset from environment, agents and seeds; reuse on hash match | the only way trajectories come to exist, so provenance is captured once |
| `data validate <dataset> --reference <file> [--dry-run]` | compare the dataset's behavioral statistics with a reference statistics file; write the report into the dataset | behavior is validated on its own before it feeds training; the reference is aggregate numbers, so nothing from outside the store is needed |
| `data stats <dataset> [--json]` | print behavioral statistics; `--json` uses the reference-file structure | quick look using the same numbers validation uses; a dataset's stats can serve as a reference |
| `model list` | id, dataset, config, seed, status, best validation loss | the population view, failures visible beside successes |
| `model inspect <model> [--json]` | manifest, checkpoints, metrics, hash checks | one model animal's complete record |
| `model train --model-config <yaml> --training-config <yaml> --dataset <id> --seed N [--dry-run]` | train one model animal; refuse on hash drift, reuse on match | one run is one id with an explicit seed; no hidden randomness |
| `model evaluate <model> --dataset <id> [--dry-run]` | frozen evaluation on a dataset's held-out split; metrics written into the model | evaluation is separate from training and never touches weights |
| `analysis record-hidden <model> --dataset <id> [--checkpoint <name>] [--dry-run]` | run standardized trajectories through a frozen checkpoint; save hidden states | post-training recording is the default; the recording is the neural data |
| `analysis axis <model> --dataset <id> [--config <yaml>] [--dry-run]` | axis-of-travel tuning per hidden unit with controls; results written into the model | the metric is defined independently of training and versioned by its config |
| `experiment list` | id, config, model count, status | populations, not single runs, answer the question |
| `experiment inspect <experiment> [--json]` | members with status, results | a population's outcome including its failures |
| `experiment run --config <yaml> [--dry-run]` | train a population from one config under one manifest, adopting members that already exist | vary one or two factors at a time under one id |
| `experiment reproduce <experiment> [--dry-run]` | verify commit, lockfile and hashes; re-run into a linked experiment; compare | reproducibility is a command, not a hope |
| `notebook new <name> [--title TEXT] [--author TEXT] [--dir DIR]` | create a Jupyter notebook from `templates/notebook.ipynb` as `src/notebooks/<date>_<slug>.ipynb` | a notebook never starts by copy-pasting; see docs/notebooks/spec.md |

### Global options and shared flags

- `--store DIR` selects the artifact store for one invocation. Without it the environment
  variable `SUBICULUM_RNN_STORE` is used; without that, the `STORE` key in
  `configs/local.yaml`; without that, `artifacts/` inside the checkout. The local file is
  the per-machine setting: git-ignored, never hashed, copied from `configs/local.example.yaml`,
  and read from the checkout so a notebook kernel sees it however it was launched.
- Configs always come from the checkout containing the package, so commands run from any
  directory.
- `--version` prints the package version, the same value every manifest records.
- `--json`, on every implemented list and inspect command, emits the same data as JSON.
- `--dry-run`, on every writing command once implemented, resolves the inputs and prints
  their hashes and the id that would be created, then writes nothing.

### Status

PR 1 implements `store init`, `store inspect`, `env list`, `env inspect`, `data list`,
`model list` and `experiment list`. `notebook new` is implemented (notebook template
PR). Every other command is a bare stub: its name and a one-line help appear in the help
tree, and running it prints "not implemented" with a pointer to this spec on stderr and
exits 3. A stub takes no arguments; they arrive with the implementation, in that
command's own PR.

### Data Model

- Configs: declarative YAML under `configs/<kind>/<name>.yaml`, addressed by name, each
  with a content hash of its resolved form.
- Store: a directory holding `store.yaml` (store version, created, hostname, tool
  version) and the kind directories `datasets/`, `models/`, `experiments/`. `store init`
  creates it; writers create subdirectories on demand. Nothing else lives in a store.
- Artifacts: `<store>/<kind>/<id>/manifest.yaml`, `id` equal to the directory name.
  Recordings, evaluations and analysis results live inside their model's directory. A
  directory without a manifest is not an artifact.
- A dataset holds raw generated trajectories (position, heading) with derived kinematics
  stored beside them, its split declared in the manifest, and any validation reports.
- Ids are scoped to a store: sequential (`ds_0001`, `rnn_000001`, `exp_0001`), derived from
  the highest existing directory of that kind, never reused, no index file. Every manifest
  also carries a random uuid and its input hash, and references upstream artifacts by id plus
  hash, so two stores handing out the same id can never be confused.
- A manifest records id, uuid, created, seeds, the name and hash of every resolved config,
  upstream ids and hashes, git commit, lockfile hash, package version and component version
  constants. The input hash combines config hashes, upstream hashes, seeds and component
  versions; commit and lockfile are recorded, not hashed.

### Behavior

- Output: a table for list, labeled lines for inspect, `--json` for the same data as JSON.
  Data to stdout, errors and progress to stderr. Ordering is sorted.
- Every writer first checks the store marker, then looks up existing artifacts by input hash
  before allocating an id; on a match it prints the existing id and writes nothing.
  `--dry-run` prints the resolved hashes and the id that would be created.
- Consumers compare the config hashes recorded in their inputs with the current configs
  and refuse on mismatch, naming the config, exit 4. `experiment reproduce` instead reports
  the drift, runs into a new experiment linked to the original, and reports the comparison.
- `experiment run` adopts an existing model whose input hash equals a member's instead of
  retraining it, and records the adoption in the experiment manifest.
- Help: the root lists groups; a group lists its commands; an implemented command shows
  its arguments and what it reads and writes; a stub says it is not implemented.
- Exit codes: 0 success, 1 no command, 2 usage error, unknown name or unusable store,
  3 not implemented, 4 provenance mismatch.

### Edge Cases

- Store path without a marker: error naming the path and how it was chosen, exit 2. For a
  path from the flag or the variable it asks whether the drive is mounted; for the default
  it says how to point elsewhere; both say to run `store init`. A marker that cannot be
  read: error naming the file and the reason, exit 2. A marker newer than the tool:
  refuse, exit 2.
- Unknown name or id: error naming it and listing what exists, exit 2. Same for a manifest
  id differing from its directory or a config that fails to resolve, naming the file and key.
- Nothing of a kind in the store: "no <kind> registered under <path>", exit 0.
- RatInABox and PyTorch are imported inside the commands that need them; a missing one
  names the pixi environment to use.

## Non-Functional Requirements

- Python 3.12, argparse from the standard library, no new dependencies. `main(argv) -> int`
  is testable in-process with `--store` at a temporary directory and runs from any directory.
- `src/cli/` package, standard argparse idioms, shared output helpers in
  one module. Stubs are rows in one table; a group gets its own module once it has a real
  command beyond `list`. Store resolution and layout live in the package, not the CLI.
- Module docstrings are one line of text on its own line between the quotes. Design and
  rationale live in this spec and the plan, not in comments.
- Tests cover the CLI's own behavior: dispatch and exit codes, store logic, what the real
  commands print. They do not test what argparse, pathlib or yaml already guarantee.

## Out of Scope

- Real behavioral data. It never enters the store or this tool. Its analysis
  happens outside the repository; at most an aggregate statistics file reaches `data validate`
  by path, and the report records only that file's checksum.
- Automatic calibration of agent configs from real statistics; the numbers are written by hand.
- Interactive prompts, TUI, colors, shell completion.
- Experiment tracking services, databases, DVC, remote or cluster launchers.
- Plotting from the CLI; figure helpers live in `src/proj_helpers/`.
- Deleting or editing artifacts; a change is a new id.
