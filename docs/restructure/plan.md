## Update after Kyle's answers, 2026-10-21

Answers: transformed about 500 MB, blocks about 100 MB. Collaborators run code on their own
machines, write their own notebooks and configs, a training run takes 30 to 60 minutes. Pixi stays.
The project is self contained: the transform step, the block step and the training pipeline all live
here, RatReplay stays as the review tool for now. Experiments must be self contained and old ones must
stay runnable.

This settles the pipeline and the plan. Plan A is the base, with three additions below.

The pipeline, three steps and their inputs

    1. transform     lab .mat files -> transformed/ (sessions, epochs, runs, frames)   exists, src/transform_lab_data
    2. build blocks  transformed/ + reviews/ + a blueprint yaml -> processed/<blueprint>/ (blocks, blocks.csv, metadata)
    3. experiment    processed/<blueprint>/ + an experiment yaml -> windows, tensors, a trained net, measures, figures

Step 2 comes back into this repository as src/axis_of_travel_rnn/blocks/, taken from RatReplay's
engines/trajectory (1,800 lines of pure functions over arrays: cuts, heading fills, registration,
labels, windows) plus a 100 line build script, pixi run build-blocks --blueprint blocks_v1. The human
decisions it needs are the review json files RatReplay writes (one small file per session, about 100
in all), which are committed under data/reviews/. That makes the blocks a pure function of three
committed things, the transformed data's manifest stamp, the reviews and the blueprint, and the
blueprint is the one place rules (cut rules, start offsets, which sessions) are set:

    configs/blueprints/blocks_v1.yaml    sessions, rules, review folder, expected data id, format version
    data/reviews/{sid}.json              the person's cuts, flags, exclusions, start offsets (from RatReplay)
    processed/blocks_v1/                 the output, outside git, rebuilt by anyone from the two above

Windows are a function, not a folder. Window settings live in the experiment yaml, windows.window_starts
runs in seconds on 100 MB of blocks, so storing them would only add a dataset to drift. The readiness
verdicts (which blocks give windows at these settings) are printed by the experiment and saved in its
results, not precomputed.

Self contained experiments and drift, the answer to the question

- An experiment is one folder, experiments/2026-10-22_window-60s/, holding config.yaml, the notebook,
  and after the run its results (metrics.csv, summary.json, figures/, the executed notebook with outputs
  as an html export). The folder is the record. It is never edited after the run, a new idea is a new
  folder, so the history reads as a lab notebook of experiments.
- Every run writes into summary.json the git commit, the package version, the blueprint name and data
  id, the resolved config and the pixi.lock hash. Those five things are what "runnable later" needs.
- To rerun an old experiment after the library moved on: git worktree add ../aot-2026-10-22 <commit>,
  pixi install there, run. The lock file pins the environment, the data id pins the data. This is the
  standard answer and it is cheap, a worktree is a second checkout, not a second clone.
- Drift is caught before it bites: a committed sample dataset (three blocks, about 2 MB, a blueprint of
  its own) and a smoke task, pixi run smoke, that runs the baseline notebook headless (papermill) on the
  sample in under a minute. It runs in the test suite, so a library change that breaks the notebook
  surface fails a test. Collaborators run it before pushing.
- The library's public surface for notebooks is small and named: load_blocks, make_windows, make_dataset,
  train, evaluate, measures, figures, save_results, each taking the config or its fields. Changes to it
  are backwards compatible or come with a version bump and a line in CHANGELOG.md. Private modules
  change freely.
- The notebook is thin: it calls those functions, holds the notes and the figures, and nothing else. A
  collaborator starts one with pixi run new-experiment "<title>", which copies the template folder with
  the baseline config.

Sharing with collaborators who run code: git clone, pixi install, then either copy transformed/ once
(500 MB, from a lab share or a bucket) and pixi run build-blocks, or copy processed/blocks_v1/ (100 MB)
and check its id. A Cloudflare R2 bucket holds both for free under 10 GB with no download fees, rclone
sync gets them, the manifest with sha256 checks them. DVC can come later if blueprints multiply.

Revised recommendation: Plan A plus the block step, the experiment folders and the smoke sample, about
five days of agent time. Order: common ground, blocks package and build script with its parity test
against the blocks RatReplay wrote (same reviews in, same parquet out), the blueprint and data id, the
library surface and config model, the sample dataset and smoke task, the baseline experiment
reproducing the 2026-10-19 notebook, the README and data dictionary.

Open for Kyle: whether the review files are committed under data/ (my recommendation, they are the
human decisions and small) or stay with the data, and whether the triple_t start offsets move from the
reviews into the blueprint as one number per session.

## What the survey found, the facts the plans rest on

- The name change is mostly done: the package is axis_of_travel_rnn, pyproject and pixi say
  axis-of-travel-rnn, only the GitHub repository is still subiculum-rnn.
- The only training code (model, trainer, dataset, axis of travel analysis, plots) is in tmp/pilot, which
  is git ignored, and src/lab_rnn (untracked) imports it. A fresh clone cannot run an experiment. The two
  newest notebooks are untracked. The first step of every plan is to put that code under version control.
- The science that stays is small: trajectory.py (block schema, kinematics, reader, 109 lines),
  windows.py (windowing, verdicts, 200 lines), tmp/pilot models, dataset, train, analysis, viz (about
  1,500 lines once the RatInABox worlds, arms and decision tables are dropped), environments/triple_t
  (geometry, for drawing and segment labels).
- The data contract is RatReplay's export: blocks/{id}.parquet, blocks.csv, metadata/{sid}.json,
  windows.json. It is described in ratreplay/README.md "The export" and in outgoing_data_schema.txt (not
  in git). lab_rnn.blocks already computes a data id as the sha256 of blocks.csv and every block.
- Nothing is shareable through git today: results, figures and run folders are ignored, notebook outputs
  are stripped. Configs are Python dicts picked by an environment variable, not yaml.
- Dependencies to drop with RatReplay and the simulation: fastapi, uvicorn, nodejs, pymc, arviz, nutpie,
  pynwb, dandi, zarr, xarray, ratinabox, einops, probably pynapple. To add: tqdm, pandas (used, undeclared).
- Stale docs: docs/cli, docs/notebooks (done), docs/process_lab_data and docs/ratreplay (removed code).
  Current: docs/transform_lab_data (the converter, incoming half of the data story).
- Sizes: src 2.6 MB (notebooks 2.1), ratreplay 138 MB, .git 17 MB, 303 tracked files of which 214 are
  RatReplay. The transformed and processed data sizes are not known to me (question 1).



## Common ground, the cleanup every plan starts with (about one day)

1. Branch agents/simplify from main after RatReplay is moved out. Delete ratreplay/, the ratreplay pixi
   feature, environment and tasks, the ratreplay entries in pyproject (wheel packages, pytest pythonpath).
2. Commit the pilot code: move tmp/pilot models.py, dataset.py, train.py (Trainer, predict, window_sse,
   persistence baseline, hidden_states), analysis.py and viz.py into src/axis_of_travel_rnn, drop
   worlds.py, sweep.py, decision.py, study.py. Merge src/lab_rnn/blocks.py (split by date, data id, read
   only guard) into the package, delete its duplicate schema. Fix every import.
3. Drop src/cli and store.py (keep notebook new as a pixi task), src/proj_helpers/lab_data_access.py.
   Keep paths.py and notebooks.py. Keep src/transform_lab_data only if the converter stays (question 4).
4. Configs: configs/local.example.yaml keeps TRANSFORMED_LAB_DATA, PROCESSED_LAB_DATA, adds RUNS. Drop
   STORE and SYNTHETIC_DATA. Window settings and thresholds become yaml under configs/.
5. Docs: delete docs/cli, docs/notebooks, docs/process_lab_data, docs/ratreplay. Keep
   docs/transform_lab_data. Write docs/data_dictionary.md as the one page contract for the blocks folder
   and windows.json (from the export section), with the format version. Rewrite README to a page.
6. Rename the GitHub repository to axis-of-travel-rnn, update the remote and the README clone line.
7. Dependencies as listed above, pixi lock regenerated, pixi run test green on the smaller test set.
8. Notebooks move to a top level notebooks/ folder, EDA ones under notebooks/eda/, nbstripout stays.

Every plan then adds its own data, config, experiment and sharing layer. Effort estimates are agent
time, with your review on top.

---

## Plan A: library plus notebooks, results in git, data by hand (lowest effort, about 3 days)

Who it suits: one person running experiments for a few weeks, two or three readers on GitHub, data
that changes once more at most. This is what goodresearch.dev recommends and what most single-lab
projects do.

Layout

    src/axis_of_travel_rnn/   data.py (read blocks, split, data id), windows.py, dataset.py (tensors,
                              scaler, leakage check), models.py, train.py, analysis.py, viz.py
    configs/                  local.example.yaml, data/blocks_v1.yaml (the blueprint), experiments/
                              baseline.yaml, window_60s.yaml ..., analysis/thresholds.yaml
    notebooks/                YYYY-MM-DD_<slug>.ipynb, one per experiment, from the template
    results/<experiment>/     committed: config.yaml as run, metrics.csv, summary.json, figures/*.png
    runs/                     ignored: checkpoints, tensors, executed notebook copies
    docs/                     data_dictionary.md, transform_lab_data/, experiments.md (an index)
    tests/                    windows, dataset leakage, model shapes, analysis measures

The data blueprint: configs/data/blocks_v1.yaml names the processed folder key, the format version,
the sessions included, the rate, the window settings and the expected data id (sha256 of blocks.csv and
the block files, computed by data.py). Loading refuses when the id differs, so every result names the
exact blocks it saw. A new scrub of NS14 to NS16 is blocks_v2.yaml with a new id. The yaml is the
blueprint, the id is the proof.

Configs: plain yaml read into a pydantic model (ExperimentConfig: data, windows, model, training,
analysis, seed). Every library function takes the model or its fields as arguments, never reads a
file itself. A notebook's first cell is tagged parameters and loads one config, so papermill can rerun
it with overrides later without any change.

An experiment, end to end: pixi run new-notebook "window 60 s" makes notebooks/2026-10-22_window-60s.ipynb.
Cells: load config, load data (id checked), build windows and tensors, train (progress in the notebook),
evaluate, analysis measures, figures. The last cell writes results/<experiment>/ with the resolved
config, the data id, the git commit and the metrics. Figures carry title, caption and the data id.

Sharing: results/ is committed, small by construction (csv, json, png under 1 MB each). A collaborator
reads the figures on GitHub or opens the notebook (outputs stripped, so they rerun it with the data).
docs/experiments.md is a table: date, notebook, config, data id, one line of outcome, link to results.
Pull requests per experiment if others contribute, otherwise commits on main.

Data hosting: none this month. The processed folder stays on your drive, collaborators get it by a
one time copy (rclone to a lab share, or a zip). A committed manifest.json (file list with sha256,
written by data.py) lets anyone check their copy. When the blocks freeze for the write up, one Zenodo
record (free, DOI, up to 50 GB) if the lab allows it, else a private R2 bucket at about $0.015 per GB
per month with free downloads.

Migration, in order: common ground, then data.py and the blueprint, then the config model, then the
training module and one baseline notebook that reproduces the 2026-10-19 result, then analysis and
figures, then results/ and the experiments index, then the README. Each step a commit with its test.

Dropped: the artifact store, the CLI, experiment tracking, data versioning tools, papermill (kept as
an option, nothing to install now).

Risks: results/ grows if figures are large (keep PNG at 150 dpi, no checkpoints). No link between a
commit and the data beyond the id, which is enough while the blocks change once. Rerunning a notebook
is the only way to compare runs, there is no dashboard.

---

## Plan B: reproducible by pull, DVC and a cheap bucket, papermill, a Quarto report (about 5 days)

Who it suits: collaborators who will run code on their own machines and want git checkout plus one
command to give them the exact data, and readers who want a rendered report rather than notebooks.

Layout, on top of Plan A

    data/processed/           DVC tracked, the blocks folder as exported (not in git, .dvc pointer is)
    data/windows/             DVC stage output: tensors or window index per blueprint
    dvc.yaml, params.yaml     the blueprint as a pipeline: stage windows (deps: blocks, params: window
                              settings) and stage dataset (deps: windows, params: rate, split)
    experiments/<name>/       papermill executed notebooks and their results, one folder per run
    reports/                  Quarto site: index, one page per experiment, rendered to GitHub Pages

The data blueprint: dvc.yaml plus params.yaml. dvc repro derives windows and tensors from the blocks,
dvc.lock records the hash of the blocks, the code and the parameters that made them. Change the
window size in params.yaml and dvc repro rebuilds only what depends on it. git log shows every data
change next to the code change. The sha256 data id of Plan A still appears in results, DVC is what
moves and verifies the files.

Data hosting: Cloudflare R2 ($0.015 per GB per month, first 10 GB free, no egress fee, S3 API, so a
10 GB dataset is free and 50 GB is $0.60 a month) or Backblaze B2 ($0.00695 per GB per month, egress
free up to three times stored). DVC remote on either. Each collaborator gets a read only key. If the
data may be public, a Hugging Face dataset repo works as the remote too and is free.

Configs: pydantic models from yaml as in Plan A. papermill parameters cell in every notebook, so
pixi run experiment baseline runs papermill with configs/experiments/baseline.yaml and writes the
executed notebook with outputs to experiments/baseline/<date>/, alongside metrics and figures. The
interactive notebook stays the way you develop, papermill is how a finished experiment is recorded.

Sharing: Quarto renders the executed notebooks to a site with freeze on, so the committed outputs
render without rerunning training. quarto publish gh-pages puts it on GitHub Pages, private to the
repository's collaborators if the repository is private (GitHub Pages on a private repo needs a paid
plan, otherwise the rendered html is committed to docs/ and read in the browser from the repository).
Collaborators who run code: git clone, pixi install, dvc pull, pixi run experiment <name>.

Migration: Plan A's steps first, since the library and the blueprint id are the same, then dvc init
and the remote, then dvc add of the blocks and the two stages, then papermill wiring and the
experiment task, then the Quarto site with the baseline page. Collaborator onboarding written as a
ten line section of the README and tried once by someone else.

Dropped: the same as Plan A. Added tools: dvc, papermill, quarto (a binary, not a Python package).

Risks: three more tools for every collaborator (DVC credentials are the usual friction). DVC changed
owners in November 2025 (lakeFS) and is stable but slower moving. Quarto freeze needs care so that a
stale output is not mistaken for a rerun. More ceremony than a two person project needs if the
collaborators only read.

---

## Plan C: tracked runs with a hosted tracker, data as a published dataset (about 4 days)

Who it suits: a group that compares many runs and wants dashboards, run histories and shareable
reports without hosting anything, and data that can live on a public or institution style host.

Layout, on top of Plan A

    results/                  as Plan A, the committed summary per experiment
    wandb/ or mlruns/         ignored, the tracker's local cache
    configs/experiments/      the same yaml configs, the tracker logs the resolved config per run

Experiment tracking: Weights and Biases academic tier (free for research, 100 to 200 GB cloud storage,
the limit has moved twice in the last year). Each notebook run calls wandb.init with the resolved config
and the data id, logs loss curves, metrics and the figures, and the analysis measures as a table.
Collaborators see every run in the project dashboard and you write W&B Reports that mix figures and
text, each with a link. Alternative with no vendor: MLflow 3 with the SQLite backend, local UI,
sharing only by running the UI on your machine or a small server (then Plan C loses its point).

Data hosting: a private Hugging Face dataset repository (free up to 100 GB, git LFS style, a
one line load in the notebook with the revision pinned to a commit hash) or, for a frozen release,
Zenodo with a DOI. If the lab's data cannot leave institutional control, this becomes the R2 bucket of
Plan B with rclone and the manifest, and the tracker still works.

The data blueprint: the same configs/data/blocks_v1.yaml and data id as Plan A, plus the dataset
revision hash in the config, so a run names both the blueprint and the exact upload.

Configs: pydantic from yaml as in Plan A, the tracker's sweep feature can drive parameter sweeps from
the same yaml (W&B sweeps), replacing papermill.

Sharing: dashboards and reports for the group, results/ in git for the record and the thesis. The
experiments index in docs/experiments.md links each row to its W&B run and report. Collaborators who
run code: clone, pixi install, huggingface-cli login, run a notebook, their runs land in the same
project.

Migration: Plan A's library and blueprint, then the tracker calls in the training module (one
function, so the tracker can be turned off by config and the library has no hard dependency on it),
then the dataset upload with its card (README in the dataset repo, the data dictionary copied there),
then the baseline notebook logged end to end, then one report.

Dropped: DVC, papermill, Quarto.

Risks: results live with a vendor whose free tier changes, and a report link rots if the account
does. Logging from notebooks needs discipline (finish every run, or the dashboard fills with
fragments). The data question (5) can rule out the hosted dataset, in which case choose Plan A or B
and add the tracker only if the group asks for it.

---

## My recommendation

Plan A now, with its blueprint and results folder, since your horizon is a few weeks and the data
changes once more. It is also the common core of B and C, so nothing is lost if the group grows: add
DVC and a bucket when a second person needs the data (B), or a tracker when run comparison becomes the
daily work (C). Decide the hosting (questions 5 and 6) when the blocks freeze, not before.
