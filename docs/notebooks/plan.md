# Notebook template plan

Read with spec.md. No code here.

## Architecture

    templates/notebook.ipynb           the template: a real notebook, placeholders in cell sources
    src/proj_helpers/notebooks.py      slugify(), git_user_name(), new_notebook(...) -> Path
    src/cli/notebook.py                register(commands): the `new` command
    src/cli/__init__.py                GROUPS gains "notebook"; the module registers
    pixi.toml                          dev deps nbformat, nbstripout, scienceplots; tasks new-jupyter-nb, nbstripout-install
    .gitattributes                     *.ipynb filter=nbstripout and diff=ipynb
    README.md                          quick start step, usage line, SciencePlots reference
    docs/cli/spec.md                   notebook row in the command table, status line
    tests/unit/test_notebooks.py       generation and no-overwrite; the git filter strips outputs

Data flow: name, slugified, gives `src/notebooks/<date>_<slug>.ipynb`. The template is read
with nbformat, `{{DATE}}`, `{{TITLE}}`, `{{NAME}}`, `{{AUTHOR}}` and `{{CREATED}}` are
replaced in every cell source, the result is written with nbformat, the path is printed.
Slug rule is the lab notebook's: lowercase, runs of non-alphanumerics become one dash,
leading and trailing dashes dropped, empty is an error. Author is `git config user.name`
unless `--author` is given; date is the local date; created is an ISO timestamp with offset.

## Implementation order

1. Dependencies and tasks in pixi.toml, `pixi install`, the attributes line.
2. The template notebook, built once with a throwaway nbformat script, committed without
   outputs, and executed once to prove every code cell runs.
3. The generator module, the CLI group module, registration.
4. The two tests.
5. README and the CLI spec row.

## Key decisions

- The template is a notebook file, not code. The generator substitutes placeholders and
  nothing else, so the template can be edited in Jupyter.
- Plain string replacement over cell sources; no templating engine.
- Output stripping is a git clean filter, editor-independent, installed per clone by a pixi
  task; the attributes line is committed so every clone gets the same behavior once installed.
- `notebook` is a real group from the start, so it has its own module per the CLI plan rule.
- Exit code 2 for an existing target or an empty slug, matching the CLI spec.
- The `no-latex` style is the default so no notebook depends on a TeX installation.
- No science, no store, no manifests: a notebook is a working document.
