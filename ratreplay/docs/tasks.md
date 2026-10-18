# RatReplay rebuild tasks

One commit per task on branch `ratreplay`, verified by `pixi run ratreplay-test` plus the listed check.
Order and dependencies are in `plan.md` (the decompressed option: the real slice first, then K, then the
synthetic slice A4, E5, E6, M3, F4). Each task names its architecture.md section in brackets. Kyle runs
anything that touches real data.

## Utilities and accesses

- [x] U1 `utilities/`: config, arrow, clock, paths, errors moved in from `arrow.py`, `clock.py`,
      `errors.py`, `stores/folder.py`. No ids utility, the access that owns a resource formats its ids, and
      `tables` arrives with A1, the first access that reads tables. Test: config returns a key or a named
      error and knows no key names. [Utilities]
- [x] A1 `access/transformed.py`, TransformedAccess from `stores/transformed.py` with the schema from
      `contract.py`. Test: health on a good, a missing and a wrong column folder names the problem. [Accesses]
- [x] A2 `access/processed.py`, ProcessedAccess from `stores/processed.py` and `stores/review.py`:
      review, write_review, blocks, block, metadata, write_blocks (temp names and rename, a session's rows
      replaced together), window_settings, write_window_settings. Test: write_blocks twice gives identical
      files, a second session is untouched, an interrupted write leaves the previous build. [Resources on disk]
- [x] A3 `access/environment.py`, EnvironmentAccess over `configs/environments/*.yaml`. Test: each kind
      loads with its geometry. [Accesses]
- [ ] A4 `access/synthetic.py`, SyntheticAccess: sets, blocks, block, write_set, delete_set, provenance
      schema. Test: write then list then delete, provenance round trips. [Accesses]

## Engines

- [x] E0 `engines/trajectory/__init__.py` with the six operation signatures (funnel added for the index), the `rules` and `settings`
      objects with today's constants as defaults, stubs that raise. Test: the layering test sees engines
      importing utilities only. [TrajectoryEngine]
- [x] E1 `funnel` and `session`: kinematics, heading offset and fills, stops, cut points, spans, occupancy, initial
      blocks, moved from `engines/cuts.py`, `heading.py`, `spans.py`, `occupancy.py` and
      `src/process_lab_data/select.py` and `frame.py`. Test: parity with the processor's cuts and fills on
      the synthetic sessions, the held fill fires on lab shaped data. [TrajectoryEngine]
- [x] E2 `apply`: the edit rules from `engines/edits.py`. Test: the existing edit tests and the parity run
      against the old tool (3,200 random edit lists), with the three deliberate refusals. [TrajectoryEngine]
- [x] E3 `blocks`: labels (trip, phase), frames to metres at the lab rate, from `src/process_lab_data/labels.py`
      and `output.py` and `src/axis_of_travel_rnn/trajectory.py`. Test: parity with the processor's blocks
      on the synthetic sessions, same call on generated arrays gives blocks in the same schema. [TrajectoryEngine]
- [ ] E4 `windows`: rows and verdicts from `src/axis_of_travel_rnn/windows.py`. Test: the existing window
      tests, a block with no window fitting, with low heading share, with no complete trip. [TrajectoryEngine]
- [ ] E5 `recipe`: the statistics (speed, turn rate, dwell, run duration, occupancy). Test: the recipe of a
      block equals hand computed numbers on a fixture. [TrajectoryEngine]
- [ ] E6 `engines/generator.py`, GeneratorEngine.session from a recipe, an environment, a seed, a length,
      explicit RNG. Test: same seed same arrays, arrays pass TransformedAccess's schema, the walk stays
      inside the environment. [GeneratorEngine]

## Managers and routers

- [ ] M1 `managers/review.py`, ReviewManager (index, load, preview, save_blocks, rebuild_all) and
      `routers/review.py`. Integration test: load, preview a refusal, save, load again gets the blocks back,
      rebuild all rebuilds two sessions, an illegal edit refuses the whole save. [ReviewManager, API]
- [ ] M2 `managers/validation.py`, ValidationManager (health, format, readiness, block, windows,
      select_settings) and `routers/validation.py`. Integration test: health names the problem, readiness
      on real and on a set, select writes windows.json whole. [ValidationManager, API]
- [ ] M3 `managers/synthesis.py`, SynthesisManager (index, generate, delete_set) and
      `routers/synthesis.py`. Integration test: generate from two source sessions writes a set with its
      provenance and both recipes, delete removes it. [SynthesisManager, API]
- [ ] L `app.py` composition root wiring the real classes, `tests/unit/test_layering.py` asserting the
      import graph of the chart, the old routers, managers, stores and engines deleted. Check:
      `pixi run ratreplay-api` serves. [Rules, Backend]

## Frontend

- [ ] F1 api client for the new routes, `state/health.ts` replacing `state/sources.ts`, Data page with
      Rebuild all, Sessions page. Check: Data page shows three folders. [Pages 1, 2]
- [ ] F2 Replay page on ReviewManager: block cards show the manager's window counts, Save blocks and its
      result toast, `session/windows.ts` deleted. [Page 3]
- [ ] F3 Blocks and Windows pages on ValidationManager: real or set, settings being tried, built settings
      shown, Select these settings. [Pages 4, 5]
- [ ] F4 Synthetic page: sets with provenance and comparison, generate, delete. [Page 6]
- [ ] F5 move `src/**/*.test.ts` to `frontend/tests/`, keep the pure modules only (timeline geometry,
      editor, keys, format), cut the rest. Check: `vitest run` green with the smaller count. [Testing]

## System tests, docs, removal

- [ ] S1 `backend/tests/system/`: save blocks, rebuild all, health, readiness through the HTTP client over
      the synthetic folders. [Testing]
- [ ] S2 `frontend/e2e/`: two or three flows (review and save, readiness and select, generate a set), the
      other specs removed. [Testing]
- [ ] R1 README and `backend/README.md` rewritten for the new tool, pixi tasks checked, `SYNTHETIC_DATA`
      in `configs/local.example.yaml`. Check: links resolve, a fresh checkout runs. [Resources on disk]
- [ ] K Kyle builds the first real dataset with the tool and reports the counts and anything wrong.
      No commit. [Core use cases]
- [ ] R2 remove `src/process_lab_data`, the `process-lab-data` task, old `src/ratreplay`, the parity
      tests that import them, `configs/datasets/lab_blocks.yaml`. Check: `pixi run test` green. [Migration]
- [ ] D debrief appended to `plan.md`: estimation accuracy, design efficacy, the work, issues to avoid,
      recurring problems, commitment to quality. [plan.md]
