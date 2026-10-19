# RatReplay rebuild plan

Read with `architecture.md`, which is the spec. No code here. This is the project design: what is built in
what order, what depends on what, where the critical path runs, and three options for the author to pick
from.

## Shape

Build by layers (architecture.md, Migration): utilities, then accesses, then engines, then managers and
routers, then pages, then the system tests. Most of the first two layers exist and are renamed and merged,
the engines are where the science moves in, the managers regroup, the pages adapt. By layers is right for
a project this small: it keeps one builder on one layer at a time and the integration points are few, at
the cost of each layer going critical, which the options below handle with float.

Two slices run through those layers. The real slice (ReviewManager, ValidationManager, their pages) is the
critical path and is used on real data as soon as it works. The synthetic slice (GeneratorEngine,
SyntheticAccess, SynthesisManager, the Synthetic page) depends only on the engine contract and the
accesses, so it has float and can run in parallel or after.

## Network

Estimates are coarse, in builder sessions (one session is a focused half day including its tests),
accuracy over precision. Letters are the tasks in `tasks.md`.

    U1 utilities (config, tables, arrow, clock, paths, ids, errors)                 1
    A1 TransformedAccess                                   after U1                 1
    A2 ProcessedAccess (review, blocks, metadata, windows.json)   after U1          2
    A3 EnvironmentAccess                                   after U1                 0.5
    A4 SyntheticAccess                                     after U1                 1
    E0 engine contract: signatures and the rules and settings objects, written first   after U1   0.5
    E1 TrajectoryEngine.session (kinematics, heading, cuts, spans, occupancy, initial blocks)   after E0, A3   2
    E2 TrajectoryEngine.apply (edit rules, parity with the old tool)   after E0    1
    E3 TrajectoryEngine.blocks (labels, metres, 20 Hz, parity with the processor)   after E1   2
    E4 TrajectoryEngine.windows (rows, verdicts)           after E0                 1
    E5 TrajectoryEngine.recipe                             after E3                 1
    E6 GeneratorEngine                                     after E0, E5             2
    M1 ReviewManager + router                              after A1, A2, E1 to E4   2
    M2 ValidationManager + router                          after A1, A2, A4, E4     1.5
    M3 SynthesisManager + router                           after A2, A4, E5, E6     1.5
    L  layering test and composition root                  after M1                 0.5
    F1 frontend: api client, state, Data and Sessions pages   after M1, M2          1
    F2 Replay page on ReviewManager                        after F1                 2
    F3 Blocks and Windows pages on ValidationManager, Select settings   after F1    1.5
    F4 Synthetic page                                      after M3, F1             1
    F5 cut the Vitest and Playwright suites to the layout, move them   after F2, F3   1
    S1 system tests: save blocks, rebuild all, health, readiness   after M1, M2, L   1
    S2 Playwright flows (two or three)                     after F2, F3             1
    R1 README, pixi tasks, remove dead code paths in the tool   after S2            0.5
    K  Kyle builds a real dataset, reports                 after R1                 (Kyle)
    R2 remove src/process_lab_data, old src/ratreplay, lab_blocks.yaml   after K    0.5
    D  debrief                                             after R2                 0.5

Critical path: U1, A2, E0, E1, E3, M1, F1, F2, F5, S2, R1, K, R2, D. About 17 sessions of builder time
plus Kyle's run. Everything on the synthetic slice (A4, E5, E6, M3, F4) and E2, E4, A1, A3, M2, F3, S1
has float against it.

God task watch: TrajectoryEngine is split into six (E0 to E5) so that no single task hides the move of
the science. E1 and E3 are the two largest and carry the parity tests, they are where the plan slips if
it slips.

Risk, Löwy's criticality model (critical 4, low float 3, medium 2, high 1, over 4N): 14 critical tasks,
7 with low to medium float, 5 with high float, about 0.73. That is inside the acceptable band (0.3 to
0.75) but above the 0.7 a normal solution should stay under, which is the usual price of building by
layers, and the reason the recommendation below is the decompressed option.

## Options

- **Normal.** One builder, by layers, in the order above. About 17 sessions on the critical path, the
  synthetic slice built in the gaps. Risk moderate: the engine layer is critical by construction, the rest
  has float.
- **Compressed, about 25 percent.** Two builders after E0: one on the real slice (E1, E3, M1, F2), one on
  the synthetic slice (E5, E6, A4, M3, F4) and the off path tasks (E2, E4, A1, A3, M2, F3). Enabling
  work: E0 becomes a real contract design task with fakes, and an integration task joins the two before
  S1. About 13 sessions, higher cost (two builders, the integration task) and more for the reviewer to
  hold at once.
- **Decompressed.** Normal, with the synthetic slice deferred until K (the first real dataset) has
  happened. The real slice reaches Kyle sooner and nothing synthetic is built on an engine contract that a
  real dataset might still change. About the same total, longer calendar, lowest risk.

Chosen 2026-10-17: decompressed. The engine contract is the thing most likely to move once real blocks
are looked at, and the synthetic slice is the thing most exposed to that move. So the order is: U1, A1,
A2, A3, E0 to E4, M1, M2, L, F1, F2, F3, F5, S1, S2, R1, then K (Kyle's first real dataset), then the
synthetic slice A4, E5, E6, M3, F4 with its tests, then R2 and D.

## Quality in the plan

Service level tests are inside each task's estimate (unit tests for the engines, an integration file per
manager). S1 and S2 are the system tests. The layering test (L) runs with every commit. Every pass is
reviewed by Opus against architecture.md before it is committed. Parity with the old processor and tool
(E2, E3) is kept until R2 removes them. D is the debrief, with the six headings in architecture.md's
checklist source: estimation accuracy, design efficacy, individual and team work, issues to avoid,
recurring problems, commitment to quality.

## What is not in this plan

Training. The converter joining RatReplay. Moving `ratreplay/` under `src/`. The Compare game. A second
client.

## Notes from the build, for the tasks ahead

- A1: `TransformedAccess.health()` assumes a root. The "key not set in local.yaml" message belongs to the
  composition root and ValidationManager (tasks L and M2), not to an access. `sessions()` returns the
  ids of the sessions with frames so ReviewManager.index (M1) does not call `session()` per row. The
  schema parity test against `contract.py` goes when L deletes `contract.py`.
- A2: the build records per block the window count and verdict at its settings in the session metadata
  (informative, readiness recomputes). The rename pass is the one window where a crash leaves a loud
  mixed state, health names it (missing, orphan and temporary files). For M1: `date` from the
  transformed sessions table is a date and the csv column is text, so the build writes `str(date)`.
  The access does not check edits (EDIT_FIELDS is description only), `TrajectoryEngine.apply` refuses
  unknown ops (E2). For M2: add a `built()` verb (sessions with metadata, including those with zero
  blocks) and an arrays-only read if readiness over all blocks is slow.
- A3: the yaml is expanded into geometry inside the access (private `environment_builders.py`), routes and
  returns were dropped (nothing on the registration path uses them, a generator derives them from the
  centerline). The old EnvSpec hash is gone, so A4 decides how a synthetic set's provenance names its
  exact geometry (store the geometry whole or hash it in the access).
- E0: a sixth operation, `funnel(tables, rules)`, so the index can say which sessions are in the dataset
  without reading frames and the session selection stays a rule in the engine. `session()` returns the
  rules it used and `apply` reads `min_block_s` and `snap_s` from there. `VERSION` is an int, M1 forms
  the metadata's `code_version` string from it and the commit. PHASES and KINDS are output vocabulary,
  E3 defines them in its labels module. Each E task removes its case from the stub test.
- E1: `session()` takes the environments as a dict by name, since a session spans arena and track.
  Positions, heading and occupancy are in room metres (the old page drew camera pixels), so F2 draws in
  metres and the occupancy grid (80 bins) reports the positions that fell outside the room. The still
  gate runs over the selected epochs only, as the processor does. Kinematics are smoothed over whole
  stretches here, the processor per block, so four frames at each block edge differ and E3 computes per
  block for parquet parity, and E3 leaves `motion` (travel direction) out of the blocks. `stops` is a
  whole session display quantity (speed under the running floor for longer than the pause minimum),
  distinct from the pause phase and from `still`. The LED swap warning needs the rat's median offset over
  other sessions, so it becomes a seventh operation over stored offsets, run by the managers on rebuild
  and on the validation pages, not inside `session()`. For Kyle: an arena only session passes the
  funnel today but cannot be registered (no track epoch), the processor crashes on it too, decide
  whether the funnel should mark it out. INITIAL_NOTE None here, "" in the old tool, E2 settles it.
- E2: `apply` returns blocks, refusals (index, op, reason), cuts and flagged runs, and ReviewManager
  assembles the review file (stamps, reviewed_by, notes) in M1. It is applied to the initial blocks with
  the whole edit list, never to saved blocks (drop and confirm toggle). An initial block's note is None,
  old review files hold "", readers treat them alike and F2 widens the type. Unknown ops are refused, not
  skipped. The 3,200 random edit list parity against the old engine and the Dash tool is now a real test
  (`tests/test_apply_parity.py`, one second) with four documented divergences allowed: reach, restores,
  too short, epoch. It goes with the oracle in R2.
- E3: blocks are at the lab rate (60 Hz) in metres, as the processor wrote them, the 20 Hz is the training
  rate the RNN project resamples to at window time (architecture.md corrected, Kyle to confirm). Block ids
  are `{sid}_{epoch}_{NN}` as the processor formed them. `kind` equals the epoch. Status stays `auto` (the
  processor wrote `automatic`, no consumer filters on it). `filled_front` and `filled_back` become
  required transformed columns, E6's generator must emit them. `blocks()` returns per block row, arrays
  and `problems` (position not finite, t steps irregular, the processor's two checks that apply and
  windows do not cover) and does not drop a block for them. For Kyle in M1: the processor failed such a
  block whole and listed it in the manifest, the alternative is to build it and let the window checks
  reject only the windows that touch the problem. The "reviewed under other rules" warning belongs to
  ReviewManager (it holds the review's saved rules).
- E4: `windows` gained a `rules` parameter, `windows(block, settings, rules)`, because the end of a trip is
  the end of the first contiguous stretch of return path ids and `return_paths` is a rule (a rule on the
  labelled columns alone was not equivalent when a return run is all pause or two return runs touch).
  The block verdict is now `{ok, reasons}` listing every broken rule (the old shape was one reason), rows
  gain `start_s`, `stop_s` and `reason`, F3 picks both up. The trip minimum applies to track blocks over
  the whole block, a window needs no trip. `settings["rate_hz"]` is unused by `windows`, it is the RNN
  project's resampling rate. Window counts use the rounded block rate, a 1e-15 s difference from the old
  code, inside the tolerance.
- M1: ReviewManager has a sixth operation `arrays(sid)` for the Arrow stream so load does not redo the
  window work. The index carries no initial block count (that needed every session's frames and a cache
  the rules forbid), the Replay page shows it on load. An excluded session can be loaded and previewed,
  only save and rebuild are refused with the funnel reason. Load re-applies a saved review's edits to
  today's initial blocks and reports refusals and a warning when the result differs from the saved
  blocks. The build uses today's RULES with the saved review and warns "reviewed under other rules" when
  they differ (for Kyle: the alternative is building with the review's saved rules). code_version is
  "trajectory {VERSION} {commit}" with the commit read once at the composition root. The manager is built
  per request from DataSources until L builds the components once. The `train_rate_hz` to `rate_hz`
  rename in schemas.py also reaches the old blocks and windows routes, which M2 replaces, and the old
  frontend's training rate field is blank until F3. Timing on a 216,000 frame session: load 184 ms,
  preview 179 ms, so no engine contract change is needed for live window counts.
- M2: ValidationManager gained `arrays(bid)` (the Arrow operation) and `selected()` (reads windows.json
  back for GET /api/windows). Readiness judges every block under the rules its session was built with,
  read from the metadata, never today's RULES. Totals carry `windows` over all blocks and `windows_ok`
  over the ok blocks. Select is refused while nothing is built. A missing config key is an `UnsetAccess`
  built at the composition root whose health names the key and whose schema still answers, so the
  manager knows no key. The run, trip and phase spans for the block player are shaped in the manager
  (run length encoding of stored labels, presentation, not a rule). `ReadinessQuery` is a WindowSettings
  subclass with `which`, because FastAPI flattens a query model only when it is the sole query parameter.
  For S1: reload through /api/health, 422 on bad query settings, routes refusing a missing folder. For
  K: time readiness on the real dataset before adding an arrays only read.
- L: the composition root builds every component once and again only on Reload, the config keys live in
  app.py alone, UnsetAccess stays in app.py as composition root code. The environments folder is the
  repository's configs/environments found from app.py's location, a config key once the tool leaves the
  repository. schemas.py is the one named exception to the arrows (recorded in Rules). A frozen fixture
  of apply's outputs on seeded edit lists is committed, since the old engine is gone and the Dash tool
  goes in R2. For Kyle and F3: the old frontend sends `train_rate_hz`, the API now refuses unknown keys
  with 422, so until F3 the Blocks page cannot set settings (it was already broken by M2's route change).
  For R1: backend/README.md and ratreplay/README.md still describe DataSources, stores and /api/sources.
- F1: the client takes the default settings from GET /api/format (the engine's SETTINGS), never a
  TypeScript constant. The gate looks at `problems`, not `exists`, since the first save creates the
  processed folder. The faithful types broke the Replay, Blocks and Windows code, so F1 made mechanical
  bridge edits there that F2 and F3 redo. For F2: delete session/windows.ts (the last window math in
  TypeScript) and show the manager's window count and verdict on the cards, the save toast names the
  review file (the backend adds the file name to the save_blocks result, the client never forms it),
  warns on build_error and failed and shows per block problems, settings live in one client store and a
  settings change refreshes the preview, the Replay gate adds environments, the header's warnings and
  refusals are shown. For F3: replace BlockView, the block header gains `rate_hz` from the backend
  (ValidationManager.block), show `windows` and `windows_ok`, the per session built settings, the
  verdict's reasons list, real or set, the row's own `ok` and `reason` instead of client comparisons
  (windowChecks goes), the Blocks and Windows gates add environments, the file name of windows.json comes
  from the API, and Rebuild all sends the selected settings when windows.json exists, else the defaults
  (today it sends the defaults, which rewrites every session's informative metadata settings).
- F2: the save result carries the review file name relative to the processed root (the access names its
  file, the client never forms a path), the session header carries the environments' geometry, warnings,
  refusals, in_dataset and reason. The map draws the epoch under the cursor's environment in metres and
  positions outside the room stay visible (a registration problem the reviewer should see), with the
  engine's `outside` count shown. `stops` and `stretches` are computed by the engine and drawn by nothing
  yet, draw them later or drop `stops`. For F3: wire `settingsStore().use()` on the Blocks page and in
  Rebuild all so the cross page settings path is live, the e2e flow spec expects an absolute review path
  (S2 decides, the API gives the relative one).
- F3: the block index row carries `rate_hz` (a fact of the build, no arithmetic in the manager or the
  engine's windows). The settings store seeds from the selection in windows.json before the API defaults,
  so a fresh load starts from what the person last chose. Rebuild all sends the selection when one
  exists, else the settings being tried, Save blocks on Replay builds at the settings being tried, the
  difference touches the informative metadata only. "Built at other settings" marks a session whose
  recorded settings differ from the ones tried, the comparison is raw over the seven fields. Select is
  disabled for a dataset other than real, F4 decides how a synthetic set's settings are selected. The
  e2e blocks, windows and flow specs target removed controls and fail until S2.
- S1: the system tests run over an empty processed folder, the fixtures no longer run the old processor
  for the client. They found and fixed one bug, a save on an unknown session was a 500, now 404. Rebuild
  all on a review whose session vanished reports a per session build_error, not an error.
- R1: both READMEs are written from the routers and the system tests. The root README gained a RatReplay
  section and the two newer config keys. The dangling docs/ links in the root README follow Kyle's
  uncommitted move of the docs tree and were left alone.
- S2: three flows (review and save, readiness and select, data and rebuild), a generate flow arrives with
  F4. The review path in the toast stays relative (review/<sid>.json), the F2 question is settled. The
  Data page keeps the previous health while it refreshes, so a test must wait for the new answer.

## Real slice done, 2026-10-18

Tasks U1 to S2 and R1 are committed, 21 commits since the docs. At the last commit: 144 backend tests
(unit, integration, system), 83 Vitest, 3 Playwright flows, 170 project tests, build green. Agent time
about 11 h against the plan's 15 to 19 h for the same tasks. Next is K.

K, for Kyle: restart the API (`pixi run ratreplay-api`, the running process predates most commits) and
rebuild the frontend (`pixi run ratreplay-build`). On the Data page the three folders should read ok. The
processed folder from the processor's runs is ignored except its `review/` files, which the tool reads,
so the index shows them as reviewed and loading one will warn "reviewed under other rules" because the
saved rule names changed. Rebuild all from the Data page builds every reviewed session into the new
layout, or review session by session with Save blocks. Then the Blocks page at the settings you want,
Select these settings, and report: the health counts, how many sessions built, failed blocks and their
problems, build errors, the readiness totals, anything that looks wrong, and how long rebuild all and
readiness took.

## K findings (Kyle's first run, 2026-10-18)

Logged as they come, fixed as tasks K1 to Kn before the synthetic slice.

- The Replay map's occupancy and geometry disagree with the trail (K1, a drawing bug: two mappings).
- Rebuild all reported an excluded session's old review as an error (K2, by design, wrong wording).
- Wanted: a page showing every environment with the stats used to create it and register sessions to
  it (K3), and the data formats on the Data page rather than the API page (K4).
- Kyle, 2026-10-18: no hard rule in the software excludes a session by a tag (group, protocol). Every
  session is listed and the person excludes, the tool records it in the review (K5). The funnel keeps
  only what the tool cannot work around. This changes which sessions enter the dataset and is Kyle's call.
- Open, to discuss after the K fixes: which geometry a session loads. Today the data chooses it, each
  epochs.csv row names its environment and the tool loads that yaml. A selector would be a person's
  override per epoch, stored in the review, and registration would follow it. It changes the science
  (which geometry anchors the registration) and waits for its own discussion.
- Proposed page shape after Kyle's first run, awaiting his yes: Incoming (a compact config strip with the
  read paths and Reload, the sessions index with stats, Exclude and Include per row, the incoming format
  collapsed), Replay, Blocks, Windows, Outgoing (the write path, what is built per session, failed and
  excluded, windows.json, Rebuild all, later the synthetic sets, the processed format collapsed), About.
- K5 (exclusion is the person's): exclude writes the review with `excluded`, `excluded_by` and
  `excluded_at` (the block review's `reviewed_by` and `reviewed_at` never change) and clears the
  session's blocks at once through the empty build, include writes the flag back and deletes a review
  that exclude alone created, so the session is exactly as before. Rebuild all lists excluded sessions
  and keeps `skipped` for reviews the funnel leaves out (no frames, a condition change). The funnel keeps
  two reasons and `annotated_exclude` is a note. On the fixtures no new session enters the dataset (the
  sessions the old rules excluded also have no frames), on the real data the JL1 and rotation protocol
  sessions appear as in the dataset until Kyle excludes them.
- Proposed with the Incoming and Outgoing shape: a Settings page after Data, so a person meets the window
  settings before the first session, with the rules shown read only (K13). Navigation would read
  Incoming, Settings, Replay, Blocks, Windows, Outgoing, Environments, About.
- Kyle, 2026-10-18: yes to the page shape. Incoming, Settings, Replay, Blocks, Windows, Outgoing,
  Environments, About, each one step of the flow in order (K7, K8, K13 as one restructuring after K11
  and K3 land).
- Kyle, 2026-10-18, note for later: the Incoming index's "Protocol" and "In dataset" columns go once the
  converter joins RatReplay and the ingestion is redone from the MATLAB files (the funnel's two remaining
  reasons become ingestion facts). Nothing changes now.
- 2026-10-18, registration finding resolved to the yaml: the paper (Olson 2017, methods and Figure 1)
  confirms the 1.6 by 1.25 m envelope, 8 cm corridors, the 60 cm arena 20 cm above the 20 cm track under
  a 2.6 m camera, LEDs 5 cm apart. The start site sits up the stem above a bottom return corridor that
  our triple_t.yaml does not have (its topology was marked inferred). K18 adds the start offset,
  measured from the data.
- K18, how to use the start offset: every built track row records `start_offset_measured_m`, the distance
  in metres up the room's y axis from the start anchor to the bottom outer corridor's occupancy peak
  (the first y peak of the running frames, the one the y scale estimate uses), at the track scale. It
  reads off the Environments page as "Start above bottom corridor, m" with its range in the ranges line.
  Read it over a few sessions, set `start_offset` in `configs/environments/triple_t.yaml` to their median,
  Rebuild all. The start then lands that far up the stem and the bottom corridor's occupancy lies on the
  outline (check it on the Replay map). The column measures the data and the track scale does not use the
  anchor, so it keeps reading the same value after the rebuild, it does not go to 0, and the x and y scale
  warning is not expected to clear from this change alone: it comes from the two scale estimates.
