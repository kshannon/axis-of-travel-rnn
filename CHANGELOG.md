# Changelog

The library's public surface (`axis_of_travel_rnn`: load_config, load_blocks, make_windows, make_dataset, train, evaluate,
measures, figures, save_results) changes only with a version bump and an entry here. Private modules change freely.

## 0.2.0, 2026-10-21

The restructure (docs/restructure/tasks.md). RatReplay, the CLI and the artifact store left the repository, the block
engine came back as `axis_of_travel_rnn.blocks` with `pixi run build-blocks`, and the training library was lifted from the
October pilot and `src/lab_rnn` into `axis_of_travel_rnn` (data, dataset, models, train, analysis, viz) with an
`ExperimentConfig` read from `configs/experiments/*.yaml`. The network is given position only and predicts the position a
horizon ahead. `save_results(results_dir, config, data_id, metrics_rows, summary, figures, started, finished)` writes an
experiment folder's summary.json, metrics.csv and figures. RatInABox is no longer a dependency.
