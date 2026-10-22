# axis-of-travel-rnn

Does an axis-of-travel-like representation emerge in a vanilla RNN trained only to predict future position? The biological
motivation is the literature describing axis-of-travel representations in the subiculum. We train recurrent networks on rat
position in a triple-T maze and look for hidden units tuned to the axis of travel. A negative result is a valid outcome. The
computational question is:
> If a simple recurrent network is trained only to predict future position from behavioral
> trajectory information, without being given an explicit axis-of-travel variable, does an
> axis-of-travel representation emerge in its hidden state?

## The pipeline

Three steps, each a function of its inputs. Paths come from `configs/local.yaml`.

1. Transform: the lab's MATLAB files become plain tables. `pixi run transform-lab-data --dry-run`, then without the flag.
2. Build blocks: the tables, the review files in `PROCESSED_LAB_DATA/review/` and a blueprint in `configs/project.yaml` become blocks.
   `pixi run build-blocks --blueprint blocks_v1` writes `PROCESSED_LAB_DATA/blocks_v1/` with a `manifest.json` and a data id.
   With P the `PROCESSED_LAB_DATA` folder, `pixi run build-blocks --blueprint blocks_v1 --compare "$P"` also compares the
   built blocks and `blocks.csv` by content with the review tool's in `$P`, prints the blocks that differ and exits 1 if any does.
3. Experiment: `pixi run new-experiment "<title>"` makes a folder under `notebooks/experiments/` (`pixi run new-experiment
   "<title>" biological` copies another config than the baseline). Run its notebook, then
   `pixi run export-experiment notebooks/experiments/<folder>/notebook.ipynb` writes `notebook.html` beside it.

The review files, a person's cuts and flags per session, are written by RatTrack, the review tool (no link yet).

## Quick start

```bash
curl -fsSL https://pixi.sh/install.sh | bash            # pixi, once per machine
git clone git@github.com:kshannon/subiculum-rnn.git     # the repository is still named subiculum-rnn on GitHub
cd subiculum-rnn
pixi install
pixi run nbstripout-install                             # once per clone: notebooks are committed without outputs
cp configs/local.example.yaml configs/local.yaml        # git-ignored, paths only, never hashed
```

Fill the four keys in `configs/local.yaml`: `LAB_DATA` (the lab's MATLAB files), `TRANSFORMED_LAB_DATA` (the tables made from
them), `PROCESSED_LAB_DATA` (the built blocks, one folder per blueprint) and `RUNS` (checkpoints and tensors, outside git).

Get the blocks, one of two ways. Copy a built `blocks_v1/` folder from a collaborator into `PROCESSED_LAB_DATA/` and check its
data id ("Share blocks"). Or build it: step 1 on the lab files, then step 2. `PROCESSED_LAB_DATA/review/` must hold the review
files, where the review tool writes them (a blueprint's `reviews` key may name another folder), a session without one is skipped.

Check the install:

```bash
pixi run smoke   # the experiment template on the committed synthetic sample in tests/fixtures/sample, headless, takes seconds
pixi run test    # the tests, and pixi run test-cov for coverage
```

## Start an experiment

`pixi run new-experiment "window 60 s"` makes `notebooks/experiments/YYYY-MM-DD_window-60-s/`. The folder holds `config.yaml` (a
copy of `configs/experiments/baseline.yaml`, or of `configs/experiments/<name>.yaml` with `pixi run new-experiment "<title>" <name>`) and `notebook.ipynb` (from
`templates/notebook-experiment.ipynb`), whose first cells hold the purpose and notes and whose last cell holds the outcome. Fill
in the purpose, edit the config, run the notebook top to bottom. Its first code cell is tagged `parameters` (`config_path`,
`results_dir`, `checkpoint_dir`), so papermill can rerun it with other values, as `pixi run smoke` does. Point `checkpoint_dir` at a folder under `RUNS` to keep the weights per epoch.

The network's inputs are a config choice (`inputs.columns`, see inputs in `DATA_DICTIONARY.md`): `configs/experiments/baseline.yaml` gives
position only, the control, and `configs/experiments/biological.yaml` adds speed, head direction and angular velocity.

- Committed: `config.yaml`, `notebook.ipynb`, `notebook.html`, `summary.json`, `metrics.csv` and `figures/`.
  `summary.json` holds the git commit, package version, blueprint, data id, resolved config, `pixi.lock` hash, times and metrics.
- Not committed: everything else in the folder (`notebooks/experiments/.gitignore`), and the contents of `RUNS`.
- A folder is never edited after its run. A new idea is a new folder.
- The notebook calls the library's surface, `help(axis_of_travel_rnn)`, which changes only with a line in `CHANGELOG.md`.
- To rerun an old one: `git worktree add ../aot-old <git_commit of its summary.json>`, `pixi install` there, run.

## Notebooks and lab notes

`pixi run new-eda "heading gaps"` makes `notebooks/eda/YYYY-MM-DD_heading-gaps.ipynb` from `templates/notebook-eda.ipynb`. Its
`parameters` cell names the project config and the blueprint, and the next cells load every block of that built folder at the
lab rate with `load_blocks`, so an exploratory notebook starts with the data in hand. `pixi run new-labnote` writes the day's
entry under `labnotebook/` from `templates/labnotebook.md`, with optional words for the file name. All three are
`templates/new.sh`, which fills the title, date and author and refuses an existing file.

## Layout

```text
configs/      project.yaml (environments, blueprints, eda, analysis thresholds), experiments/ (one file per preset),
              local.example.yaml (copy to local.yaml)
docs/         blocks_schema.md, pilot.md, restructure/ and transform_lab_data/ (DATA_DICTIONARY.md sits at the root)
labnotebook/  the authors' dated log, pixi run new-labnote
notebooks/    working notebooks, eda/ for the exploratory ones, experiments/ one folder per experiment (config, notebook, results)
src/          axis_of_travel_rnn/ (the library, config.py for paths and configs, blocks/ the block engine with geometry.py),
              transform_lab_data/ (the converter)
templates/    notebook-eda.ipynb, notebook-experiment.ipynb, labnotebook.md and new.sh
tests/        unit/, integration/ (the smoke) and fixtures/ (sample/, a synthetic built folder for the smoke, committed,
              and make_sample.py, which rebuilds it)
tmp/          uncommitted scratch and planning
```

## Where the data lives

| what | where | in git |
| --- | --- | --- |
| the lab's MATLAB files | `LAB_DATA` | no |
| transformed tables and frames (about 500 MB) | `TRANSFORMED_LAB_DATA` | no |
| blocks (about 100 MB) | `PROCESSED_LAB_DATA/<blueprint>/` | no |
| review files | `PROCESSED_LAB_DATA/review/` | no |
| synthetic sample | `tests/fixtures/sample/` | yes, no real recording |
| checkpoints and tensors | `RUNS` | no |
| experiment records | `notebooks/experiments/<folder>/` | yes, the files listed above |

The rule: the data lives outside the repository, which holds no data folder. Real recordings, transformed frames, review files
and block parquet files never enter it. Git tracks code, configs, docs, tests (the synthetic sample with them), the experiment
records and `pixi.lock`.

A result names what made it, all in its `summary.json`: the git commit (code), the `pixi.lock` hash (environment), the blueprint
and data id (data), the resolved config (configuration) and the seed in it (model).

## Share blocks

`rclone` is not a project dependency, install it yourself. The bucket or lab share is not chosen yet (`docs/restructure/plan.md`
names a Cloudflare R2 bucket), so `remote:bucket` is a placeholder. Use `copy`, not `sync`, so nothing is deleted on either side.
The review files travel with the processed folder: when `PROCESSED_LAB_DATA` is synced, copy its `review/` folder with it, as
it holds the human decisions a build reads.

```bash
rclone copy /path/to/processed-lab-data/blocks_v1 remote:bucket/blocks_v1 --checksum --progress   # upload
rclone copy remote:bucket/blocks_v1 /path/to/processed-lab-data/blocks_v1 --checksum --progress   # download
rclone copy /path/to/processed-lab-data/review remote:bucket/review --checksum --progress         # the review files, both ways alike
```

After a download, recompute the data id. It must equal the blueprint's `expected_data_id` and the `data_id` in the folder's
`manifest.json`.

```bash
pixi run python -c "
from pathlib import Path
from axis_of_travel_rnn.blocks.__main__ import data_id
print(data_id(Path('/path/to/processed-lab-data/blocks_v1')))"
grep -A 20 "^  blocks_v1:" configs/project.yaml | grep expected_data_id
```

## The pilot

Before touching real data, an October 2026 pilot tried to make axis of travel tuning appear in a constrained artificial
setting: a vanilla RNN trained on simulated RatInABox worlds, a square loop and an open field, with thresholds fixed before any
network was trained. Its pre registered decision came out no-go, with the comparison arms never run, so it stands as a trial of
the method rather than a proof. The library's models, trainer and analysis measures were lifted from it. Its code, tests and
notebook are kept on branch `pilot`, see `docs/pilot.md` for what it was and what it found.

## Docs

- `DATA_DICTIONARY.md`: what every attribute and term means, raw, transformed and built blocks, with units and sources.
- `docs/blocks_schema.md`: the review, block and manifest files, their columns and keys in order, the blueprint keys and defaults.
- `docs/pilot.md`: the October 2026 pilot on simulated worlds, what it found and where its code lives.
- `docs/restructure/`: the plan, the tasks and the debrief of the restructure that made this pipeline.
- `docs/transform_lab_data/`: the converter's spec, plan, tasks and `tables.md` (the lab's files and the transformed tables).

## Citation

If you use this code, please cite the relevant papers (see project wiki for full reference list of papers and open source citable libraries).

**Cite this project**: `¯\_(ツ)_/¯` One Day!
