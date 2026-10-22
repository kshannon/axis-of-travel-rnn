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

# 5. Machine-local paths go in configs/local.yaml (git-ignored): copy the example
#    and edit it, see "Machine-local paths" below.
cp configs/local.example.yaml configs/local.yaml
```

## Using the project

The command line and the artifact store were removed in the restructure (docs/restructure/). What is left are
pixi tasks:

```bash
pixi run transform-lab-data    # convert the lab's MATLAB files to tables, see "Converting the lab data"
pixi run new-labnote [slug words]   # new lab notebook entry
pixi run new-jupyter-nb <name>      # new Jupyter notebook from the template, named by date and slug
pixi run test                       # the tests, and pixi run test-cov for coverage
```

New notebooks come from `templates/notebook.ipynb` and draw their figures in
the SciencePlots<sup>4</sup> style. git stores every notebook without its
outputs, so `pixi run nbstripout-install` belongs in every clone.

## Machine-local paths

`configs/local.yaml` holds the paths that depend on the machine, nothing else:
`LAB_DATA` for the lab's recordings, `TRANSFORMED_LAB_DATA` for the tables made
from them and `PROCESSED_LAB_DATA` for the blocks built from those. The file is
git-ignored. Copy `configs/local.example.yaml` and edit. Nothing in it is
ever hashed, so two machines with different drives produce identical results.

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

## Blocks and training

The step that turns the converted tables into training ready blocks is done by a separate review tool for now, and
the training code is still being brought under version control. The plan for moving both into this repository is in
[docs/restructure/](docs/restructure/). No recorded animal data lives in this repository.

## Layout

```
configs/         declarative YAML; environments today, blueprints and experiments as they land
src/
  axis_of_travel_rnn/  the core package: the block schema, kinematics, the block reader and the window rules
  environments/        parametric geometry (triple-T, open arena), content hashes, RatInABox adapter
  proj_helpers/        machine-local paths, new notebooks and lab notes from the templates
  transform_lab_data/  the lab data converter (docs/transform_lab_data/), `pixi run transform-lab-data`
notebooks/       the working Jupyter notebooks, notebooks/eda/ for the exploratory ones
templates/       the notebook and lab notebook templates
datasets/        datasets on disk, git-ignored
tests/           unit tests
docs/            per-feature spec, plan and tasks (transform_lab_data/, restructure/)
labnotebook/     dated entries, `pixi run new-labnote`
```

## Replicability and Reproducibility

There is a complex history of these tertms and what they mean within different fields, especially with the rise of computation being essential to most research. Here I will use the National Academies<sup>1</sup> definition of these terms, which the Association for Computing Machinery<sup>2</sup> also agrees:

- **Replicability**: An attempt by a second researcher to replicate a previous study is an effort to determine whether applying the same methods to the same scientific question produces similar results.
- **Reproducibility**: obtaining consistent results using the same input data, computational methods, and conditions of analysis.


Synthetic data and open source data results should be reproducible. Results using your own collected recording data should be replicable to within some stated percision. Given the stochastic nature of machine learning methods, from data cleaning to pipeline construction to training and validation, it can be daunting to provide near 100% reproducibility, but it is a standard to strive for nonetheless.

To that end, this README provides all instructions needed to reproduce our synthetic data results. Instructions for reproducing results with open-source data and our own recorded data are provided in the project wiki.


| Requirement                            | How it's met                                                                                                                                  |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Exact software versions**            | `pixi.lock` pins every Python package, and its transitive dependencies, to a specific version                                                 |
| **Versioned data provenance**          | Each set of blocks carries a manifest and a data id (planned, docs/restructure/)                                                              |
| **Logged and versioned training runs** | Every experiment is a folder with its config, results and a summary of commit, data id and lockfile (planned, docs/restructure/)             |
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

Git tracks code, configs, docs, tests, the lab notebook and `pixi.lock`. It does not track data, `figures/`,
checkpoints, or anything regenerable from configs, code and seeds.


## Citation

If you use this code, please cite the relevant papers (see project wiki for full reference list of papers and open source citable libraries).

**Cite this project**: `¯\_(ツ)_/¯` One Day!

---

1. National Academies of Sciences, Engineering, and Medicine. 2019. Reproducibility and Replicability in Science. Washington, DC: The National Academies Press. https://doi.org/10.17226/25303.
2. https://www.acm.org/publications/policies/artifact-review-and-badging-current
3. Tom M George, Mehul Rastogi, William de Cothi, Claudia Clopath, Kimberly Stachenfeld, Caswell Barry. "RatInABox, a toolkit for modelling locomotion and neuronal activity in continuous environments" (2024), eLife, https://doi.org/10.7554/eLife.85274 .
4. John D. Garrett. "garrettj403/SciencePlots", Zenodo, https://doi.org/10.5281/zenodo.4106649 .
