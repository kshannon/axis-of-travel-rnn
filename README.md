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
2. Build blocks: the tables, the review files in `data/reviews/` and a blueprint in `configs/blueprints/` become blocks.
   `pixi run build-blocks --blueprint blocks_v1` writes `PROCESSED_LAB_DATA/blocks_v1/` with a `manifest.json` and a data id.
3. Experiment: `pixi run new-experiment "<title>"` makes a folder under `experiments/`. Run its notebook, then
   `pixi run export-experiment experiments/<folder>/notebook.ipynb` writes `notebook.html` beside it.

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
data id ("Share blocks"). Or build it: step 1 on the lab files, then step 2. `data/reviews/` must hold the review files, a
session without one is skipped (the folder is empty until step 12 of `docs/restructure/tasks.md` is done).

Check the install:

```bash
pixi run smoke   # the experiment template on the committed synthetic sample, headless, takes seconds
pixi run test    # the tests, and pixi run test-cov for coverage
```

## Start an experiment

`pixi run new-experiment "window 60 s"` makes `experiments/YYYY-MM-DD_window-60-s/`. The folder holds `config.yaml` (a copy of
`configs/experiments/baseline.yaml`), `notebook.ipynb` and `README.md`. Fill in the purpose, edit the config, run the notebook
top to bottom. Its first code cell is tagged `parameters` (`config_path`, `results_dir`, `checkpoint_dir`), so papermill can
rerun it with other values, as `pixi run smoke` does. Point `checkpoint_dir` at a folder under `RUNS` to keep the weights per epoch.

The network's inputs are a config choice (`inputs.columns`, see `docs/data_dictionary.md`): `configs/experiments/baseline.yaml` gives
position only, the control, and `configs/experiments/biological.yaml` adds speed, head direction and angular velocity.

- Committed: `config.yaml`, `README.md`, `notebook.ipynb`, `notebook.html`, `summary.json`, `metrics.csv` and `figures/`.
  `summary.json` holds the git commit, package version, blueprint, data id, resolved config, `pixi.lock` hash, times and metrics.
- Not committed: everything else in the folder (`experiments/.gitignore`), and the contents of `RUNS`.
- A folder is never edited after its run. A new idea is a new folder.
- The notebook calls the library's surface, `help(axis_of_travel_rnn)`, which changes only with a line in `CHANGELOG.md`.
- To rerun an old one: `git worktree add ../aot-old <git_commit of its summary.json>`, `pixi install` there, run.

## Layout

```text
configs/      YAML: blueprints/, experiments/, analysis/, environments/, local.example.yaml (copy to local.yaml)
data/         reviews/ (the review json files) and sample/ (a synthetic built folder for the smoke), both committed
datasets/     datasets on disk, git-ignored (the pilot writes here)
docs/         data_dictionary.md, glossary.md, restructure/ and transform_lab_data/
experiments/  one folder per experiment: config, notebook and results
labnotebook/  the authors' dated log, pixi run new-labnote
notebooks/    working notebooks, eda/ for the exploratory ones
pilot/        the October 2026 pilot kept for later, not imported by the library, its tests not collected
scripts/      compare_blocks.py (two built folders by content), make_sample.py (rebuilds data/sample)
src/          axis_of_travel_rnn/ (the library, blocks/ is the block engine), environments/ (maze geometry),
              proj_helpers/ (paths, new experiments, notebooks, notes), transform_lab_data/ (the converter)
templates/    experiment/, notebook.ipynb and labnotebook.md
tests/        unit/ and integration/ (the smoke)
tmp/          uncommitted scratch and planning
```

## Where the data lives

| what | where | in git |
| --- | --- | --- |
| the lab's MATLAB files | `LAB_DATA` | no |
| transformed tables and frames (about 500 MB) | `TRANSFORMED_LAB_DATA` | no |
| blocks (about 100 MB) | `PROCESSED_LAB_DATA/<blueprint>/` | no |
| review files | `data/reviews/` | yes |
| synthetic sample | `data/sample/` | yes, no real recording |
| checkpoints and tensors | `RUNS` | no |
| experiment records | `experiments/<folder>/` | yes, the files listed above |

The rule: real recordings, transformed frames and block parquet files never enter the repository. Git tracks code, configs,
docs, tests, the review files, the sample, the experiment records and `pixi.lock`.

A result names what made it, all in its `summary.json`: the git commit (code), the `pixi.lock` hash (environment), the blueprint
and data id (data), the resolved config (configuration) and the seed in it (model).

## Share blocks

`rclone` is not a project dependency, install it yourself. The bucket or lab share is not chosen yet (`docs/restructure/plan.md`
names a Cloudflare R2 bucket), so `remote:bucket` is a placeholder. Use `copy`, not `sync`, so nothing is deleted on either side.

```bash
rclone copy /path/to/processed-lab-data/blocks_v1 remote:bucket/blocks_v1 --checksum --progress   # upload
rclone copy remote:bucket/blocks_v1 /path/to/processed-lab-data/blocks_v1 --checksum --progress   # download
```

After a download, recompute the data id. It must equal the blueprint's `expected_data_id` and the `data_id` in the folder's
`manifest.json`.

```bash
pixi run python -c "
from pathlib import Path
from axis_of_travel_rnn.blocks.__main__ import data_id
print(data_id(Path('/path/to/processed-lab-data/blocks_v1')))"
grep expected_data_id configs/blueprints/blocks_v1.yaml
```

## Docs

- `docs/data_dictionary.md`: the review, block and manifest files, their columns and keys, the data id, the blueprint.
- `docs/glossary.md`: the terms (clean run, pause, heading offset and the rest).
- `docs/restructure/`: the plan, the tasks and the debrief of the restructure that made this pipeline.
- `docs/transform_lab_data/`: the converter's spec, plan, tasks and `tables.md` (the lab's files and the transformed tables).

## Citation

If you use this code, please cite the relevant papers (see project wiki for full reference list of papers and open source citable libraries).

**Cite this project**: `¯\_(ツ)_/¯` One Day!
