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
- [x] E4 `windows`: rows and verdicts from `src/axis_of_travel_rnn/windows.py`. Test: the existing window
      tests, a block with no window fitting, with low heading share, with no complete trip. [TrajectoryEngine]
- [ ] E5 `recipe`: the statistics (speed, turn rate, dwell, run duration, occupancy). Test: the recipe of a
      block equals hand computed numbers on a fixture. [TrajectoryEngine]
- [ ] E6 `engines/generator.py`, GeneratorEngine.session from a recipe, an environment, a seed, a length,
      explicit RNG. Test: same seed same arrays, arrays pass TransformedAccess's schema, the walk stays
      inside the environment. [GeneratorEngine]

## Managers and routers

- [x] M1 `managers/review.py`, ReviewManager (index, load, preview, save_blocks, rebuild_all) and
      `routers/review.py`. Integration test: load, preview a refusal, save, load again gets the blocks back,
      rebuild all rebuilds two sessions, an illegal edit refuses the whole save. [ReviewManager, API]
- [x] M2 `managers/validation.py`, ValidationManager (health, format, readiness, block, windows,
      select_settings) and `routers/validation.py`. Integration test: health names the problem, readiness
      on real and on a set, select writes windows.json whole. [ValidationManager, API]
- [ ] M3 `managers/synthesis.py`, SynthesisManager (index, generate, delete_set) and
      `routers/synthesis.py`. Integration test: generate from two source sessions writes a set with its
      provenance and both recipes, delete removes it. [SynthesisManager, API]
- [x] L `app.py` composition root wiring the real classes, `tests/unit/test_layering.py` asserting the
      import graph of the chart, the old routers, managers, stores and engines deleted. Check:
      `pixi run ratreplay-api` serves. [Rules, Backend]

## Frontend

- [x] F1 api client for the new routes, `state/health.ts` replacing `state/sources.ts`, Data page with
      Rebuild all, Sessions page. Check: Data page shows three folders. [Pages 1, 2]
- [x] F2 Replay page on ReviewManager: block cards show the manager's window counts, Save blocks and its
      result toast, `session/windows.ts` deleted. [Page 3]
- [x] F3 Blocks and Windows pages on ValidationManager: real or set, settings being tried, built settings
      shown, Select these settings. [Pages 4, 5]
- [ ] F4 Synthetic page: sets with provenance and comparison, generate, delete. [Page 6]
- [x] F5 move `src/**/*.test.ts` to `frontend/tests/`, keep the pure modules only (timeline geometry,
      editor, keys, format), cut the rest. Check: `vitest run` green with the smaller count. [Testing]

## System tests, docs, removal

- [x] S1 `backend/tests/system/`: save blocks, rebuild all, health, readiness, the session header with
      query settings, the Arrow arrays, preview, and a 422 on a malformed edit, through the HTTP client
      over the synthetic folders. [Testing]
- [x] S2 `frontend/e2e/`: three flows (review and save, readiness and select, data and rebuild all), the
      other specs removed. A generate flow arrives with F4. [Testing]
- [x] R1 README and `backend/README.md` rewritten for the new tool, pixi tasks checked, `SYNTHETIC_DATA`
      in `configs/local.example.yaml`. Check: links resolve, a fresh checkout runs. [Resources on disk]
- [ ] K Kyle builds the first real dataset with the tool and reports the counts and anything wrong.
      No commit. [Core use cases]
- [ ] R2 remove `src/process_lab_data`, the `process-lab-data` task, old `src/ratreplay`, the parity
      tests that import them, `configs/datasets/lab_blocks.yaml`. Check: `pixi run test` green. [Migration]
- [ ] D debrief appended to `plan.md`: estimation accuracy, design efficacy, the work, issues to avoid,
      recurring problems, commitment to quality. [plan.md]

## K findings, fixed before the synthetic slice

- [x] K1 Replay map: the occupancy image was drawn mirrored in y (a negative height in drawImage does not
      flip in Chromium), the trail and the outline were right. The image now lands row by row from the
      top through the one projection. Vitest on the backdrop placement, a check on
      the synthetic circle. [Page 3]
- [x] K2 Rebuild all skips the reviews of sessions the funnel leaves out and lists them as skipped with
      the reason, not as errors. The toast says so. [ReviewManager]
- [x] K3 Environments page: every environment with its yaml parameters, its geometry drawn, and per built
      session the registration it was given (scale, rotation, LED offset and separation, warnings) from
      the metadata. Read only. [new page, ValidationManager]
- [x] K4 The data formats move from the API page to the Data page, the API page is removed, its OpenAPI
      schema becomes an "Under the hood" section of About (a cheat sheet of the internal routes, not a
      public API). Kyle, 2026-10-18. [Pages 1, 7 and 8]
- [x] K5 Exclusion is the person's: the funnel drops `protocol` and `excluded_groups` and keeps only "no
      frames" and "no arena or track epoch under the condition", the review file gains `excluded` with a
      note, who and when, ReviewManager gains `exclude(sid, excluded, note)`, an excluded session is not
      built and Rebuild all lists it as excluded, the Sessions index and Replay get Exclude and Include,
      `annotations.csv` exclude shows as a note and is not applied. Decided by Kyle 2026-10-18. [funnel,
      ReviewManager, Pages 2 and 3]
- [x] K6 Data page loses the data flow line (room for the cards). About page: no "more" panel, "what this
      is" carries the rules it follows, a section on what a person can do and what each action writes
      (from the files' point of view), and the main section is the process, the workflow and instructions
      for use, including the data flow. Kyle, 2026-10-18. [Pages 1 and 8]
- [x] K9 Status marks and palette: the ok, problem and nothing yet states on the Data page become a strong
      coloured mark with a plain word and a coloured edge on the card, and the palette tries the San Diego
      Gulls colours used sparingly, marine blue #0083BF as the accent and ok, orange #FF4C00 only for a
      problem or a refusal, silver #C0CDD5 for muted text, black and white as the grounds of the two
      themes. The margin spans on the timeline are drawn light in the dark theme (they were black on
      black). Kyle, 2026-10-18. [UX rules, Page 1 first]
- [x] K10 The Sessions totals line becomes a one row strip of small tiles (in the dataset, reviewed,
      excluded, blocks confirmed, confirmed hours per kind, built), numbers large, labels muted. Folds into
      Incoming (K7) if that shape is taken. Kyle, 2026-10-18. [Page 2]
- [x] K11 Replay layout and errors: the block editing buttons (marks, split, new block, edges, accept,
      reject, remove) move onto the timeline card in one row under the lanes, notes and flag a run go
      under the playback, names get a plainness pass. Errors and warnings move to the top right, larger,
      with the time, stacked newest first, each closed by hand, successes stay brief. Flag a run stays
      unless Kyle drops it. The zoom controls become one segmented block on the timeline card, Reset view,
      plus, minus, Zoom to block, in that order. The runs lane is made less tall. A block bar too narrow for "block 5" shows "5" alone, and nothing when
      even that does not fit. The heading chips and lanes say whose work it is: "head dir interpolated by
      RatReplay", "head dir held by RatReplay", "head dir missing", and "lights filled by the lab" for the
      converter's light fills, the same words on the cards, the Windows page and the About guide. The cut chips become "recording
      paused", "tracking lost", "position jumped", "margins trimmed", and the layer toggles move to a narrow
      side panel on the timeline card, each with one line of what it means and the rule's number read from
      the session's rules. The map layer choice (occupancy, current, all, arena, track) becomes a row of
      checkboxes under the map title, each layer on or off on its own (occupancy, geometry, arena, track,
      trail), "follow the cursor's epoch" a checkbox too, nothing forced on. Kyle, 2026-10-18.
      [Page 3, UX rules]
- [x] K12 The verdict strings are written for a person, in the engine so every page says the same: "head
      dir measured on 75% of frames, the setting needs 80%", "no window of 40 s fits in this block",
      "0 complete trips, the setting needs 1", each naming the setting that decides it, the window
      row's reason likewise, and the Blocks page settings fields get a one line hint of what each setting
      protects. Tests and e2e strings follow. Kyle, 2026-10-18. [TrajectoryEngine.windows]
- [x] K13 Decided by Kyle 2026-10-18: a Settings page after Incoming, the seven window settings with a hint and
      the default each, the spelled out sentence, Select these settings and the selection, reset to the
      defaults, and the engine's rules read only with their meanings. Blocks keeps a compact read only
      line with a link. Lands with K7 and K8 as one restructuring. [Pages]
- [x] K7 Decided by Kyle 2026-10-18: the Incoming page replaces Data and Sessions. A compact config strip
      (the lab data read path, the environment geometry read path, the config file, Reload, a status dot
      each, problems unfold only when there are any), the sessions index with the K10 tiles, details,
      Exclude and Include, Open in replay, the incoming data format collapsed at the bottom. [Pages]
- [x] K8 Decided by Kyle 2026-10-18: the Outgoing page after Windows. The block write path with its
      status, per session the blocks built, the settings they were built with, failed blocks and their
      problems, excluded and skipped sessions, the selected windows.json, Rebuild all with its
      confirmation, later the synthetic sets, the processed data format collapsed at the bottom. [Pages]
- [x] K14 The Replay trail is drawn from the engine's smoothed position (the Savitzky-Golay position
      kinematics already uses for speed), handed out by `session()` as display arrays beside the raw x
      and y, never into the blocks, and the trail is drawn a little wider. Kyle, 2026-10-18.
      [TrajectoryEngine.session, Page 3]
- [x] K15 Environments page redesign: one environment shown large with its parameters, ranges and its
      sessions table in a vertically scrolling area, the other environments as a row of thumbnails about
      the size of today's drawings to pick from, no unused space. Kyle, 2026-10-18. [Page 7]
- [x] K16 Incoming strip: ok gets its own green (the accent stays marine blue), the status mark reads
      cleanly in both themes, Reload moves to the card's top right as an icon button "Reload config
      file" so the rows align, and the note reads "If you update the config file, or change its location,
      you will need to reload it to view data". Kyle, 2026-10-18. [Page 1]
