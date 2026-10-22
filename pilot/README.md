# The October 2026 pilot

This is the pilot study from October 2026. Its brief was `tmp/documents/pilot.md`, which lives outside git.
It is restored here as it was from branch `feature/pilot`, last commit `63d5734` of 2026-10-13
("WIP: pilot study, saved as is"). Nothing was edited.

It is kept as a separate folder to be dealt with later. The library `axis_of_travel_rnn` does not import it,
and `pixi run test` does not collect its tests (pytest only looks in `tests/`).

- `pilot/` is the package (worlds, dataset, models, train, analysis, viz, sweep, decision, study, `thresholds.yaml`)
- `tests/` holds its 90 tests
- `notebooks/2026-10-13_pilot.ipynb` is the pilot notebook

To run its tests, if someone must: `PYTHONPATH=pilot pixi run python -m pytest pilot/tests`
It needs `proj_helpers`, `tqdm` and `ratinabox`, and ratinabox is no longer in the pixi environment, so its world tests need `pixi add --pypi ratinabox` first or are skipped. The tests write to temp folders.
Run outside the tests, the pilot reads and writes `datasets/pilot/`.
