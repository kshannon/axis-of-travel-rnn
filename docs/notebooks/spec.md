# Notebook template

PR on branch `agents/notebook-template`: one command that creates a Jupyter notebook in
`src/notebooks/` from a standard template, so a new notebook never starts by copy-pasting.

## Overview

`axis-of-travel-rnn notebook new <name>` copies `templates/notebook.ipynb` to
`src/notebooks/YYYY-MM-DD_<name>.ipynb`, filling in the title, date and name. The template is
a real notebook, edited in Jupyter like any other, so changing what every new notebook
starts with means editing one file, not code. A notebook is a working document, not an
artifact: nothing here touches the store or manifests.

## Functional Requirements

### Command

- `axis-of-travel-rnn notebook new <name> [--title TEXT] [--author TEXT] [--dir DIR]`: create
  the notebook and print its path. `<name>` is slugified the way `pixi run new-labnote` slugifies lab notebook
  names (lowercase, runs of non-alphanumerics become one dash). `--title` defaults to the
  name with dashes turned into spaces. `--author` defaults to git's `user.name`. `--dir`
  defaults to `src/notebooks/` in the checkout.
- `pixi run new-jupyter-nb <name>` is the same command as a pixi task.
- Refuses to overwrite: an existing file at the target path is an error naming it, exit 2.
  An empty slug is an error, exit 2.
- The `notebook` group joins the CLI spec's command table; it is the first group whose
  only command is real.

### Template contents, in cell order

1. Markdown header: `# <date> <title>`, then author, notebook name, created timestamp,
   and a Purpose line to fill in.
2. Code, setup: `%load_ext autoreload`, `%autoreload 2`, `%matplotlib inline`,
   `%config InlineBackend.figure_format = "retina"`; imports: `Path`, `numpy as np`,
   `pandas as pd`, `matplotlib.pyplot as plt`, `scienceplots` (registers the styles),
   `axis_of_travel_rnn`, `load_environment` and `list_environments` from the environments
   package, `resolve_store` from the store; `plt.style.use(["science", "notebook",
   "no-latex"])`; `rng = np.random.default_rng(0)`; `store = resolve_store(None)`; a
   context print of package version, git commit, store path and today's date.
3. Code, sample figure in the SciencePlots style: two panels, the triple-T walls drawn
   from `load_environment("triple_t")` with equal aspect, and a line plot with a legend;
   a `FIGURES = Path("figures")` and a commented `fig.savefig(FIGURES / ..., dpi=300)`.
4. Markdown section headers with a one-line hint each: Data, Analysis, Figures, Notes.

Placeholders in the template are `{{DATE}}`, `{{TITLE}}`, `{{NAME}}`, `{{AUTHOR}}` and
`{{CREATED}}`, replaced in every cell's source. Everything else is copied verbatim. The
template is committed without outputs like every notebook; run its cells once after opening.

### Behavior

- Outputs never enter git. `nbstripout` is installed as a git clean filter, once per clone
  with `pixi run nbstripout-install`; `.gitattributes` marks `*.ipynb` for it. The working
  copy keeps its outputs; only the committed file is stripped. A finished notebook is
  shared as an export (PDF or HTML), not as saved outputs.
- Notebooks are small and many: one question per notebook, rather than one large one.
  Cheap creation is what makes that the easy path.
- LaTeX is not required: `no-latex` is in the default style list. Remove it in a notebook
  when a TeX installation is present and publication typography is wanted.

## Non-Functional Requirements

- `src/proj_helpers/notebooks.py` holds one function, `new_notebook(name, title, directory,
  today)`, reading and writing through `nbformat`; `cli/notebook.py` is the group module.
- Dependencies, dev feature only: `nbformat` (already present through jupyter, declared
  explicitly), `nbstripout`, and `scienceplots` from PyPI. `nbformat` is imported inside the function so
  the CLI's import cost does not change.
- SciencePlots is credited in the README references with its Zenodo citation
  (John D. Garrett, garrettj403/SciencePlots, doi 10.5281/zenodo.4106649) and in the PR.
- Two tests. The generated file validates with `nbformat`, its first cell contains the
  date, title and author, and a second call with the same name exits 2. And in a temporary
  git repo carrying the project's attributes line and the install task's command, a
  notebook committed with outputs is stored without them.

## Out of Scope

- Executing notebooks or parameterizing them (papermill).
- Exporting a finished notebook to PDF or HTML: its own small feature. PDF needs pandoc
  plus LaTeX or a headless browser; HTML needs nothing extra.
- Subfolders under `src/notebooks/`; `--dir` covers other locations.
- Registering notebooks in the store or linking them to artifacts.
- A LaTeX installation or the `ieee` and `nature` styles.
