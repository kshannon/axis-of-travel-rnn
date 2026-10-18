# axis-of-travel-rnn

This repository contains a computational neuroscience research project investigating whether axis-of-travel-like representations can emerge spontaneously in a simple recurrent neural network (RNN) trained to predict an animal's future position during spatial navigation. The biological motivation is the literature describing axis-of-travel representations in the subiculum. The computational question is:
> If a simple recurrent network is trained only to predict future position from behavioral
> trajectory information, without being given an explicit axis-of-travel variable, does an
> axis-of-travel representation emerge in its hidden state?


## Quick start

```bash
# 1. Install pixi (one-time)
curl -fsSL https://pixi.sh/install.sh | bash

# 2. Clone
git clone git@github.com:kshannon/subiculum-rnn.git
cd subiculum-rnn

# 3. Install environment, dependencies and the project package (editable)
pixi install
pixi run nbstripout-install   # once per clone: notebooks are committed without outputs

# 4. Check it works
pixi run test
pixi run axis-of-travel-rnn env list

# 5. Choose where artifacts live: artifacts/ in this checkout by default,
#    or a directory elsewhere, for example on an external drive. Machine-local
#    paths go in configs/local.yaml (git-ignored); copy the example and edit it,
#    see "Machine-local paths" below.
cp configs/local.example.yaml configs/local.yaml
pixi run axis-of-travel-rnn store init     # creates the store named in local.yaml
pixi run axis-of-travel-rnn store inspect
```

## Using the project

- The `axis-of-travel-rnn` command orchestrates everything
- Commands are grouped by layer, and every group and command has `--help` with what it reads, what it writes and an example.

```bash
pixi run axis-of-travel-rnn --help                      # the groups: store, env, agent, data, model, analysis, experiment, notebook, labnote
pixi run axis-of-travel-rnn store inspect               # where artifacts go, marker, counts
pixi run axis-of-travel-rnn env list                    # environment configs and geometry hashes
pixi run axis-of-travel-rnn env inspect triple_t --json # one environment; the JSON is exactly what gets hashed
pixi run axis-of-travel-rnn data list                   # registered datasets in the store
pixi run axis-of-travel-rnn model list                  # registered models (model animals)
pixi run axis-of-travel-rnn experiment list             # registered experiments (populations)
pixi run new-labnote [slug words]                       # new lab notebook entry
pixi run new-jupyter-nb <name>                          # new Jupyter notebook from the template, named by date and slug
```

`pixi run test-cov` runs the tests with coverage. `python -m axis_of_travel_rnn` is the same as the
`axis-of-travel-rnn` command, and `store inspect`, `env list` and `env inspect` take `--json`.

Artifacts (datasets, models, experiments) are written only by this command,
into a store outside git: `--store DIR` for one run, the `SUBICULUM_RNN_STORE`
variable, the `STORE` key in `configs/local.yaml`, or `artifacts/` in the
checkout by default. A store is a
directory with a `store.yaml` marker; commands refuse anything else, which
catches an unplugged drive. Each artifact carries a manifest recording the
configs and hashes, seeds, git commit and lockfile that produced it, so it is
regenerable and never modified in place.

New notebooks come from `templates/notebook.ipynb` and draw their figures in
the SciencePlots<sup>4</sup> style; git stores every notebook without its
outputs, so `pixi run nbstripout-install` belongs in every clone.

## Machine-local paths

`configs/local.yaml` holds the paths that depend on the machine, nothing else:
`STORE` for the artifact store, `LAB_DATA` for the lab's recordings,
`TRANSFORMED_LAB_DATA` for the tables made from them, `PROCESSED_LAB_DATA` for
the reviews and blocks RatReplay builds and `SYNTHETIC_DATA` for synthetic sets
(RatReplay's synthetic slice, not built yet). It is git-ignored; copy
`configs/local.example.yaml` and edit. The first three paths are resolved in one
order: the command-line flag, then the environment variable (`SUBICULUM_RNN_STORE`,
`SUBICULUM_RNN_LAB`, `SUBICULUM_RNN_TRANSFORMED_LAB`), then this file, then the
built-in default. RatReplay reads its keys from this file only. Nothing in it is
ever hashed into a manifest, so two machines with different drives produce
identical artifacts.

## Converting the lab data

The lab's MATLAB recordings are converted once into plain tables so the rest of
the work never touches MATLAB: `sessions.csv`, `epochs.csv`, `runs.csv` and
`events.csv`, one Parquet file of per-frame tracking for each session under
`frames/`, and `manifest.json` and `checks.json` recording what was written and
what each check found. The converter reorganizes the lab's own segmentation and
checks it; it does no analysis. A session that fails a check is reported and the
others still convert. The recordings and the tables stay outside the repository.

Before running, set both paths in `configs/local.yaml` (see "Machine-local paths"
above): `LAB_DATA`, the folder of lab MATLAB files, and `TRANSFORMED_LAB_DATA`,
the folder the tables are written to. The converter reads these two keys from
that file only, and exits 2 naming the problem if one is missing, `LAB_DATA` is
not a folder, or the output folder is inside the lab folder or this repository.

```bash
pixi run transform-lab-data --dry-run      # list sessions, skipped files and the files it would write; writes nothing
pixi run transform-lab-data                # convert every session
pixi run transform-lab-data --sample 2     # only the first 2 sessions per subject
pixi run transform-lab-data --only NS14    # only sessions whose id starts with NS14
```

Do the dry run first. A real run exits 0 when every selected session was
written and 1 when any failed. Each run rewrites the tables, so a run with
`--only` or `--sample` leaves tables for just those sessions; to start clean,
delete the output folder. Details are in [docs/transform_lab_data/](docs/transform_lab_data/).

## RatReplay

RatReplay, in `ratreplay/`, is the review tool for the converted tables, a localhost app with its own backend and
frontend. A person replays each session in the browser and confirms or edits its blocks, and saving builds them in
metres with trip and phase labels into the folder `PROCESSED_LAB_DATA` names, beside the `windows.json` of the window
settings selected for export, which the RNN training reads as files. Block building has moved from the processor into
RatReplay, so `pixi run process-lab-data` is retired and removed in task R2, once the first real dataset has been built
with the tool. How to run and use it is in [ratreplay/README.md](ratreplay/README.md).

## How synthetic data will be generated

No recorded animal data lives in this repository or its store. Behavior is
synthetic, and the generator is planned, not built: an environment config
(triple-T track, open arena) fixes the geometry; an agent config will fix a
behavioral profile, meaning speed, turning and dwell statistics and a goal
policy; a dataset config will name an environment, agents, sessions and
trials, seeds, and a split policy. `data generate` will turn that into
trajectories of position and heading, store velocity, speed and angular
velocity derived from them beside the raw arrays, and record every config hash
and seed in the dataset's manifest. `data validate` will compare the dataset's
behavioral statistics against an aggregate reference-statistics file and write
the report into the dataset. Only position will reach the RNN during training;
heading and kinematics exist for validation and controls. Today those commands
are stubs that exit 3; the contract is [docs/cli/spec.md](docs/cli/spec.md).

## Layout

```
configs/         declarative YAML; environments today, datasets, models, training and experiments later
src/
  axis_of_travel_rnn/  the core package; store.py is the artifact store: resolution order, marker, layout, manifest scan
  cli/                 the command line entry point: groups, stub table, real commands
  environments/        parametric geometry (triple-T, open arena, plus maze), content hashes, RatInABox adapter
  proj_helpers/        machine-local paths, lab data access, new notebooks and lab notes from the templates
  transform_lab_data/  the lab data converter (docs/transform_lab_data/), `pixi run transform-lab-data`
  notebooks/           the working Jupyter notebooks
ratreplay/       RatReplay, the review tool: backend, frontend and docs (ratreplay/README.md)
templates/       the notebook and lab notebook templates
datasets/        datasets on disk, git-ignored; synthetic/
tests/           unit tests for the store and the CLI
docs/            per-feature spec, plan and tasks (cli/, transform_lab_data/, process_lab_data/, notebooks/)
artifacts/       the default store: datasets, models, experiments (git-ignored, regenerable)
labnotebook/     dated entries, `pixi run new-labnote`
```

## Replicability and Reproducibility

There is a complex history of these tertms and what they mean within different fields, especially with the rise of computation being essential to most research. Here I will use the National Academies<sup>1</sup> definition of these terms, which the Association for Computing Machinery<sup>2</sup> also agrees:

- **Replicability**: An attempt by a second researcher to replicate a previous study is an effort to determine whether applying the same methods to the same scientific question produces similar results.
- **Reproducibility**: obtaining consistent results using the same input data, computational methods, and conditions of analysis.


Synthetic data (generated with the RatInABox python library<sup>3</sup>), and open source data results should be reproducible. Results using your own collected recording data should be replicable to within some stated percision. Given the stochastic nature of machine learning methods, from data cleaning to pipeline construction to training and validation, it can be daunting to provide near 100% reproducibility, but it is a standard to strive for nonetheless.

To that end, this README provides all instructions needed to reproduce our synthetic data results. Instructions for reproducing results with open-source data and our own recorded data are provided in the project wiki.


| Requirement                            | How it's met                                                                                                                                  |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Exact software versions**            | `pixi.lock` pins every Python package, and its transitive dependencies, to a specific version                                                 |
| **Versioned data provenance**          | Each synthetic dataset has a manifest with all generation parameters, seeds, the environment geometry hash and an ID                          |
| **Logged and versioned training runs** | Every dataset, model and experiment is a directory under `artifacts/` with a `manifest.yaml` recording config, seed, code commit and lockfile |
| **Cross-platform**                     | `pixi.toml` targets `linux-64`, `osx-arm64`                                                                                                   |

These versioning layers are recorded separately and never conflated:

| layer                  | identified by                       |
| ---------------------- | ----------------------------------- |
| code                   | git commit                          |
| environment (software) | `pixi.lock`                         |
| environment (geometry) | config name plus `EnvSpec.hash`     |
| dataset                | dataset id and manifest             |
| model configuration    | config file under `configs/models/` |
| model instance         | model id, seed, checkpoint          |
| analysis               | analysis config plus code commit    |

Git tracks code, configs, docs, tests, the lab notebook and `pixi.lock`. It does not track the store
(`artifacts/` or wherever `SUBICULUM_RNN_STORE` points), `figures/`, checkpoints, or anything regenerable from
configs, code and seeds.


## Citation

If you use this code, please cite the relevant papers (see project wiki for full reference list of papers and open source citable libraries).

**Cite this project**: `¯\_(ツ)_/¯` One Day!

---

1. National Academies of Sciences, Engineering, and Medicine. 2019. Reproducibility and Replicability in Science. Washington, DC: The National Academies Press. https://doi.org/10.17226/25303.
2. https://www.acm.org/publications/policies/artifact-review-and-badging-current
3. Tom M George, Mehul Rastogi, William de Cothi, Claudia Clopath, Kimberly Stachenfeld, Caswell Barry. "RatInABox, a toolkit for modelling locomotion and neuronal activity in continuous environments" (2024), eLife, https://doi.org/10.7554/eLife.85274 .
4. John D. Garrett. "garrettj403/SciencePlots", Zenodo, https://doi.org/10.5281/zenodo.4106649 .
