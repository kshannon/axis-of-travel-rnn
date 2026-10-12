# Notebook template tasks

One commit per task on `agents/notebook-template`, verified by `pixi run test` plus the
listed command. Spec sections in brackets.

- [x] T1 pixi.toml: dev dependencies `nbformat`, `nbstripout`, `scienceplots` (PyPI); tasks
  `notebook` and `nbstripout-install`; `pixi install`; `.gitattributes` gains the
  `*.ipynb` filter and diff lines. Verify: `pixi run python -c "import scienceplots,
  nbstripout, nbformat"`. [Non-Functional, Behavior]
- [x] T2 `templates/notebook.ipynb` with the four cells of the spec, no outputs.
  Verify: `pixi run jupyter nbconvert --execute --to notebook --stdout
  templates/notebook.ipynb > /dev/null` succeeds. [Template contents]
- [x] T3 `src/proj_helpers/notebooks.py` and `cli/notebook.py`, group registered.
  Verify: `pixi run axis-of-travel-rnn notebook new smoke test` creates
  `src/notebooks/<date>_smoke-test.ipynb`; the same command again exits 2; remove the file. [Command]
- [x] T4 `tests/unit/test_notebooks.py`: generated notebook validates and its header holds
  date, title and author; second call exits 2; a notebook with outputs committed in a
  temporary repo using our attributes and install command is stored stripped.
  Verify: `pixi run test`. [Non-Functional]
- [x] T5 README: `pixi run nbstripout-install` in quick start, `pixi run new-jupyter-nb <name>` in
  usage, SciencePlots in references; `docs/cli/spec.md`: notebook row and status.
  Verify: links resolve, `axis-of-travel-rnn --help` lists the group. [Command, Non-Functional]
