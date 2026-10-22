# Changelog

The library's public surface (`axis_of_travel_rnn`: load_config, load_blocks, make_windows, make_dataset, train, evaluate,
measures, figures, save_results) changes only with a version bump and an entry here. Private modules change freely.

## Unreleased

The configs collapsed to `configs/project.yaml` plus `configs/experiments/`. An experiment config's `analysis.thresholds` names a
section of the project config, `analysis.thresholds` by default, and a yaml path still works. A build's manifest records the
sha256 of the blueprint's own section in canonical json. No version bump yet.

## 0.2.0, 2026-10-21

The restructure (docs/restructure/tasks.md). The web review tool, the CLI and the write-once store left the repository, the block
engine came back as `axis_of_travel_rnn.blocks` with `pixi run build-blocks`, and the training library was lifted from the
October pilot and `src/lab_rnn` into `axis_of_travel_rnn` (data, dataset, models, train, analysis, viz) with an
`ExperimentConfig` read from `configs/experiments/*.yaml`. The network is given position only and predicts the position a
horizon ahead. `save_results(results_dir, config, data_id, metrics_rows, summary, figures, started, finished)` writes an
experiment folder's summary.json, metrics.csv and figures. A blueprint's `built` key names a built folder inside the
repository, which `load_blocks` reads with no configs/local.yaml, as the committed sample in tests/fixtures/sample does. RatInABox stays a dependency for a block data viewer to come.
