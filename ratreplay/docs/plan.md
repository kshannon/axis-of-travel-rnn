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

## Synthetic slice design, 2026-10-19

Branch `agents/synthetic` off `ratreplay`. Kyle asked for the `SYNTHETIC_DATA` folder, a first pass of the
generator with a page to sample synthetic blocks from the built real blocks, and a page that shows a
real and a synthetic block side by side and lets the person guess which is real. The architecture's
A4, E5, E6, M3 and F4 cover the first three, F6 is the quiz page.

The science choices, Kyle's to overturn, each recorded in the set's provenance:

- The recipe (E5) is per block kind. Speed and turn rate as quantiles (5, 25, 50, 75, 95) and mean,
  the still fraction under the running floor, the heading spread as the circular standard deviation of
  heading minus direction of motion while running, pause durations and pauses per minute. Track adds
  run durations per path id, dwell durations at the start and at a goal, trips per minute, the share
  of outbound runs per goal (path 1 to 4), and the share of time per phase. Arena adds the distance to
  the boundary as quantiles and the occupancy over a 10 by 10 grid of the room. Counts: blocks, frames,
  seconds. The same function runs on the synthetic blocks, so the comparison is the two recipes side by
  side.
- The generator (E6) writes a session in the transformed schema, camera pixels and two LEDs, so the
  synthetic session goes through the same registration, cuts, fills, labels and windows as a real one.
  It is given a camera (scale, rotation, flip, offset, LED separation) taken from the source session's
  registration, a rate of 60 Hz, a max_gap of 30, one arena epoch then one track epoch, each of the length
  asked for. No tracking loss, no jumps, every light on: the first pass generates clean behavior, the
  cuts then find nothing to cut.
- Track behavior is a sequence of trips over the centreline graph. A goal is drawn by the recipe's
  share per path, outbound is the shortest path along the centreline from the start to the goal,
  return is the shortest path from the goal back to the start over the perimeter (the graph without the
  stem, the crossbars and the approaches), so it runs out through the connector and the top and down a
  side. Path ids by goal, an assumption to check against the lab's numbering: 1 g_ww, 2 g_we, 3 g_ew,
  4 g_ee, return 9 down the west side, 10 down the east side. A run's duration is drawn from the
  recipe's run durations for that path, the speed along it is a smooth bell (accelerate, cruise, brake)
  scaled to cover the path in that time, with low noise. Dwells at the goal and at the start are drawn
  from the recipe. A slow lateral wander inside the corridor keeps the rat off the centreline. Heading is
  the direction of motion plus von Mises noise with the recipe's spread, and wanders slowly while still.
  Every run is clean, the runs table carries them with their path ids so the labels and the start site
  registration work as on real data.
- Arena behavior is a correlated random walk: speed follows an AR(1) process matched to the recipe's
  quantiles, turn rate is drawn from the recipe's distribution, the walk turns away from the boundary
  within a margin, pauses occur at the recipe's rate and last its durations.
- The quiz (F6) draws one real block and one synthetic block of the same kind, shows both as a trail on
  the map with playback and the speed trace, no ids, no runs and no path ids, in a random order. The
  person says which is real, the server reveals and records the guess in the set's `guesses.json`
  (when, who, the two blocks, the guess, correct), and the page shows the tally for the set. The
  SynthesisManager keeps the open pairs in memory, keyed by an opaque id, so the page never holds the
  block ids before the reveal. That is the one piece of state a manager holds, lost on restart, which
  only closes unanswered pairs.
- A synthetic set is one generated session blocked with the same `TrajectoryEngine.blocks` call, kept
  under `synthetic/sets/{set_id}/` with `blocks.csv`, `blocks/{block_id}.parquet`, `provenance.json`
  and `guesses.json`, the block files in the processed schema. Block ids start with the set id, so
  ValidationManager finds a block in the sets when the processed folder lacks it, and readiness on
  `set:{id}` reads that set. Set ids are `syn_{YYYYMMDD}_{HHMMSS}_{seed}`.

Not in this pass: tracking loss and jumps in synthetic sessions, a learned model of behavior, more than
one session per set, generator parameters beyond seed and length, pauses on the track outside dwells.

Decided in the review of the first backend pass (2026-10-19), Kyle's to overturn:

- The direction of motion is each frame's step to the next, in the recipe and in the generator alike, and
  a frame with a zero step (or one under the running floor) has no direction, so pixel quantised tracking
  adds no spurious residual. The generator's track heading is that step direction plus the noise, its
  arena heading is the walk's angle with the noise on the step, so heading spread round trips in both.
- An arena pause is a still stretch (speed under the running floor for over `pause_min_s`, the rule the
  session's stops use), since the labels paint no pause in the arena. The arena's `phase_share.pause`
  stays, reading 0, as the labels say. The track's pauses stay the painted phase.
- The arena's boundary distance and occupancy grid are measured against the environment's boundary and
  room, so real and synthetic share one frame.
- Dwells are still (a 2 mm jitter with a 3 s time constant) and the heading turns from the way in to the
  way out over 1 s. The lateral wander bends rather than jitters, so the track heading is not jagged.
- The speed and turn rate of the arena walk take the recipe's quantiles through a Gaussian copula, so the
  marginal matches. The recipe's pauses are drawn on top, which double counts stillness (measured pauses
  per minute and still fraction run high). Known residual mismatches on the hand made test recipe: the
  track turn rate IQR comes out about 1.4 against 1.0 (the heading noise time constant, 2 s, is not fitted
  to the turn rate), the arena's about 2.5 against 1.6 (the steering away from the boundary in a 0.6 m
  arena). Whether to fit the noise time constant to the turn rate is open.
- The quiz serves only `x`, `y`, `heading`, `speed` and the kind, environment, length, rate and geometry
  per side (`t` was dropped in the review of the frontend pass, a real block keeps its offset in the
  session and a synthetic one starts near zero). The real block is drawn from the environment the set was
  generated in, since a source in another environment would show through the backdrop. Two tells are
  left, both Kyle's to decide on: a real block's lost heading (NaN), visible in playback, and the block
  length, since a real block runs as long as its epoch allowed and a synthetic one as long as was asked
  for, so the two timelines end at different times. The options are to show only the first N seconds of
  both sides or to trim both to the shorter one.
- The block format moved to `utilities/blocks.py`, shared by the processed folder and the synthetic sets,
  so no access imports another.

Generator version 2 (K35, 2026-10-19), after Kyle's first quiz on real data, Kyle's to overturn:

- The recipe adds `lateral_m` (track, quantiles of the distance to the nearest centreline segment over frames at or
  over the running floor), `speed_cv_run` (track, per run the standard deviation over the mean of the speed over the
  middle 60 percent of its frames, the median over runs), `speed_cv` (arena, the same over running stretches of 1 s or
  more), `tracking_noise_m` (both, the spread of the second difference of the block's x and y over sqrt(6), on the
  block's raw room positions, the smoothed ones being only for drawing), `heading_spread_by_speed` (speed bins with
  edges 0, 0.05, 0.1, 0.17, 0.25, 0.35, 0.5 m/s, each with its median speed, spread and frame count) and
  `heading_lag_s`. The last two read heading against the Savitzky-Golay direction of motion, not the step to the
  next frame as the brief said: with 2 mm of tracking noise the step's direction is noise at a walk (it put the
  spread at 0.3 m/s 50 percent high) and its turn rate is noise at any speed, which drove the lag to zero. The lag
  is the regression over frames at 0.2 m/s or more. `heading_spread_rad` stays on the step and so reads high
  wherever there is tracking noise.
- The generator. Track runs: duration drawn from the recipe times a lognormal pace (sigma 0.2), a raised cosine
  bell times an AR(1) modulation (spread `speed_cv_run`, 1 s), a hesitation with chance 0.3 (0.3 to 0.8 s down to a
  third of the cruise, in the middle half), renormalised to the run's length. Lateral offset: two smooth AR(1)
  processes (3 s and 0.5 s, equal variance) with a total spread of the `lateral_m` median over 0.6745, at most half
  the clip, faded in and out over 5 cm at a run's ends, clipped at the half corridor plus the LED half separation.
  Corners: a centred moving average over 0.25 s per run, the window shrinking at the ends so a run starts and ends
  on its sites. Dwells: a smooth AR(1) wander (5 cm along the corridor, the lateral spread across, 1 s) that stands
  during still stretches (mean 1.5 s) covering the recipe's still fraction over its dwell phase share (0.05 to
  0.8), faded to the site over 0.3 s at each end. Excursions, not runs: with chance 0.25 after a start dwell, down
  the stem and 0.2 to 0.8 of the way along a bottom segment and back, and with chance 0.15 after a goal dwell, up
  its connector and back, each leg at the recipe's q75 speed. Every track position is pulled back within the clip
  of the centreline at the end.
- Heading: the travel direction is the tangent of the path smoothed over 0.1 s, held through dwells and under the
  running floor, turned toward the next run over a dwell's last second and limited to 2 pi rad/s (an excursion's
  turnaround otherwise flipped the head in one frame). The heading is that direction delayed by `heading_lag_s`
  plus a smooth AR(1) noise whose spread follows the speed through `heading_spread_by_speed` (smoothed over
  0.25 s). The noise time constant is 0.5 s, not the 0.15 s asked for: at 0.15 s a still head (spread near 145
  degrees) moved about 16 degrees a frame, at 0.5 s the median frame change is 2.6 degrees on the track (real about
  2). The arena walk's steps follow its angle, and its heading comes from the path the same way.
- Tracking noise: Gaussian pixel noise on both LEDs giving the midpoint the recipe's `tracking_noise_m`, one tenth
  of its variance drawn for each LED alone and the rest shared. All of it independent per LED, as asked, made the
  heading jitter by about 7 degrees a frame and the turn rate seven times the recipe's. The arena speed gets an AR(1)
  modulation of spread `speed_cv` (0.5 s).
- Round trip on a hand made recipe (900 s track, 300 s arena, seed 7, out over in): lateral median 0.78 (q95
  0.97), speed_cv_run 0.91, arena speed_cv 1.19, tracking noise 1.01 and 1.00, run duration medians 1.10 and 0.95,
  dwell medians 1.30 and 1.16, still fraction 0.88 and 1.06, speed median 0.86, the spread by speed within 20 percent
  from 0.07 m/s up on the track (the arena reads 25 percent high above 0.3 m/s), lag 1.01 on the track and 0.63 in
  the arena, no frame pair turning over 90 degrees. Left: `heading_spread_rad` 1.6 to 1.8 times (the step direction
  under noise, above), the turn rate 3.5 to 4 times the invented literal (it is not fitted, the real median frame
  change is the better target), and arena pauses per minute 0 against 2: the speed noise of a still rat under 2 mm
  of tracking noise is about 0.02 m/s, so a still stretch rarely stays under the 0.03 floor for 1 s. Real blocks
  carry the same effect in their own recipe.
- Registration on short sessions: the wider lateral spread and the noise broaden the corridor occupancy peaks, so on
  a session of 3 minutes about one seed in five misses the top corridor's peak (the axes warning), one in twenty at
  10 minutes, none in twenty at 20 minutes. The registration is untouched.

Generator version 3 (K36, 2026-10-20), after Kyle's second quiz on real data and his comparison table on NS14_rec9_20141210_002,
Kyle's to overturn. Numbers are out over in on a real shaped literal (scratchpad k36/lib.py: his centreline distance
quantiles, dwell medians, speeds, turn rates and boundary distance, the rest invented), seed 7, 20 minutes of track and 10 of
arena, version 2 before the arrow and version 3 after.

- The recipe adds `lateral_outward_m` (track, quantiles of the offset from the nearest centreline segment over running
  frames, on the perimeter (`side_`, `bottom_`, `top_`, `conn_`) and on the inner segments). The sign is taken along the
  segment's normal pointing away from the room's centre at its midpoint, not along the line from the centre to the foot
  point as the brief said: the stem lies on a line through the centre, where that dot product is zero. `reversals_per_min`
  (both kinds) is the brief's rule: the Savitzky-Golay direction of motion turned by over 120 degrees from 0.5 s earlier,
  the speed at or over the running floor on both frames, counted once a second. It reads 27 a minute on version 2, which
  makes no reversals: dwell jitter at 3 cm/s, a run setting off back the way an excursion came, and the U from a
  crossbar up a rise into an approach. So the track adds `run_reversals_per_min`, the same rule with both frames in one run
  and the straight distance between them under half the path the speed covers, which reads 0.3 a minute on version 2.
  The generator fits that one, each back and forth being two turns. The comparison shows both.
- Lean: on perimeter segments the offset along the outward normal is the class mean plus the wander with the class spread
  (interquartile range over 1.349, at most half the clip), inner segments the same with their numbers, the dwell moves
  leaning as the corridor they walk into. On the generator's own positions the perimeter lean inside runs is 0.013 for a
  recipe mean of 0.015. Measured back through the registration it is about half the recipe's (0.010 for 0.020): the
  registration puts the outer occupancy peaks on the centreline, so a symmetric outward lean is taken out as scale, and
  the scale reads 1.6 to 1.8 percent high (max 2.3). A real session's lean is measured through the same registration.
- Registration, 20 seeds each, axes warnings at 10 and at 20 minutes of track. Test recipe (perimeter spread 1.5 cm):
  0 and 0 before, 0 and 0 after, scale error median 0.6 then 1.7 percent, max 2.2. Real shaped literal with a narrow
  perimeter spread (1.5 cm): 11 and 15 before, 2 and 0 after. With the spread made to agree with the real centreline
  distance (perimeter median 2 cm outward, spread 3 cm): 11 and 16 after, so the lean alone does not fix it. On a failing
  seed (0, 20 minutes) the y peaks taken are the bottom corridor, the crossbar and the approach row (0.83 m up, smoothed
  height 2333, where the four goals and their dwells sit). The top corridor (1.19 m, height 226, prominence 127) falls
  under the 10 percent cutoff of 233, so y reads 0.71 of true. The registration rules are untouched, Kyle's to decide.
- Reversals: during a run or an excursion, with the chance the recipe's run rate over two over the share of time in runs
  for its duration, the rat turns back for 0.5 to 2 s at the run's pace (a 0.3 s turn each way, in the middle half), the
  run lengthened by it and still one run row, clean False. Run reversals 1.26 for 1.0, and every run marked not clean
  shows one.
- Dwells (c): a dwell is still stretches as before and between them moves along the corridors meeting at the site, out
  0.1 to 0.3 m in one moving stretch, standing, back in the next. A move out and back in one stretch turned the travel
  direction a full circle each time. The move speed bound matters little since a 0.1 to 0.3 m move over a mean 4.75 s
  stretch walks at about 4 cm/s, so the wander keeps its 5 cm. Speed q25 0.78 to 0.77, q50 0.90 to 0.91, still fraction
  1.06 to 1.11. q25 stays 23 percent low. On this literal version 2's speed median was already 0.15 for 0.17, not Kyle's
  0.10, as its runs are not his.
- Dwell draw (point 2): left as it was. Over six seeds the start dwell median reads 1.18 for a drawn 0.52 (the excursions
  count into the dwell), the goal 11.4 for 9.9. On the e2e fixture sessions' recipe, start 1.65 for 1.65, goal 10.15 for
  10.0, version 2 and 3 alike (the plan draws in the same order).
- Heading (a): the noise time constant per kind from the closed form (a smooth AR(1) of spread s and time constant tau
  turns at s over tau times sqrt(2 over pi), the travel direction's own rate taken off in quadrature), times 1.5 from a
  search over the factor, the spread smoothed over 0.5 s (was 0.25). Turn rate, mean absolute: arena 2.35 to 0.96, track
  2.50 to 1.67. The track cannot get lower this way: with no heading noise at all it reads 1.66 (the route corners, the
  turn at each leg of a dwell move, the dwell wander), so tau sits at its 5 s bound. Heading spread 1.50 to 1.40 on the
  track, 1.36 to 1.40 in the arena (on the step direction, high wherever there is tracking noise). Putting the spread
  inside the filter instead lost the lag and raised the spread to 1.8, so it was dropped.
- Arena (b): the walk steers toward the tangent at a target distance from the wall, drawn from `boundary_distance_m` and
  held 2 to 6 s, turned in or out by the arctangent of the radial error over 5 cm, the midpoint never past the boundary
  (the recipe's distance is unsigned, so a point outside would read inside, and the brief's allowance of the LED half
  separation is not used). Boundary distance q05, q50, q95: 0.061, 0.123, 0.234 to 0.003, 0.025, 0.082 for 0.00, 0.03,
  0.07. The modulated speed is mapped back by rank onto the recipe's quantiles: speed q95 0.49 to 0.37 for 0.40. The
  arena's registration anchors the median position at the room centre, so a rat on one side of the wall in a short epoch
  shifts the arena offset (10 cm on a 2 minute epoch, 2 to 3 cm on 10 minutes), real or synthetic.
- Centreline distance (d), now registered: q25, q50, q75, q95 of 0.8, 1.8, 4.2, 9.5 cm read 0.8, 1.8, 3.4, 5.8 cm (version
  2, mis-registered, 2.4, 5.6, 9.1, 19.6). The tail cannot pass the clip at the half corridor and the LED half separation.

## Debrief, 2026-10-20

Times come from commit stamps, a coarse clock: commits were batched (five in one second on 10-19 at 03:25) and nights show
as gaps, so an interval bounds the work only when it is short. The rebuild is 64 of the branch's 97 commits (the first 33
are the converter rename, the processor, the first Dash tool and the first RatReplay build), from the docs commit on 10-17
at 23:23 to K38 on 10-20 at 08:57: 57.6 h elapsed, 13.2 h of it in commit gaps under two hours.

### Estimation accuracy
- Unit. The plan counted in sessions of a focused half day, a human builder's unit. After the real slice the note converted
  the 23 sessions of U1 to R1 to 15 to 19 h of agent time and recorded about 11 h, 0.6 to 0.7 of the estimate. The stamps
  agree: 10.3 h from the docs commit to the slice's last commit, 6.5 h of it the night between F1 (02:39) and F2 (09:06). In
  the unit as written it would be about 11 days, so no task can be read against its sessions.
- Backend and frontend. U1 to L is 12 commits in 2 h 47 min against 15 sessions. E1 and E3, the tasks the plan said would
  slip, landed 23 and 19 min after the commit before them. F2 sits in the night gap and cannot be told from sleep, and F2,
  F3, S1, F5, R1 and S2 were committed within 34 min, so they were built before they were committed. The risk score of 0.73
  priced the build, and the build was the cheap part.
- The K round was not estimated, the plan had one line, "Kyle builds a real dataset, reports", and no number. It produced 39
  findings and 36 of the 64 commits: 33 on 10-18 between 10:17 and 23:46 (13.5 h elapsed, more than the slice it followed)
  and K35, K36 and K38 later. That is 1.8 times the slice in commits, the ratio to carry next time.
- Synthetic slice. A4, E5, E6, M3 and F4 were 6.5 sessions, and F6 (the quiz page) and S3 (its flow) joined them unplanned.
  One workflow run built them, 1.4 h from the design commit to the five commits stamped within a second. E5 and E6 were then
  redone as generator versions 2 and 3 (K35, K36), 20 h and 21 h after. A generator is done when it matches real behavior,
  so its estimate was a guess.

### Design efficacy
- Layering bought one builder on one layer and an import graph pinned by `test_layering.py`. Of K1 to K34, 7 touched an
  engine (K5, K12, K14, K20, K23, K33, K34, by my reading of the task lines). The page restructure (K7, K8, K13) cost pages
  only, and the synthetic slice went in as an access, a manager, a generator engine and two pages, the recipe filling an
  operation the contract already held, which the decompressed order protected.
- Pure engines bought parity against the old tools until they went (3,200 random edit lists in E2, the processor's blocks in
  E3, a frozen fixture now). The generator's session goes through the same `blocks` call as a real one and the recipe is one
  function run on both, so registration could be tested on synthetic data over 20 seeds, which is how K36 was found.
- The format version rule: the page began comparing at 1 on 10-18 at 12:01, the rule was written at 19:26 for the heading
  span shape (2), then 3 for the start offset and 4 for the synthetic folder. Each bump turned a missing key into "restart
  the API". It does not catch changed values under one shape (K38's float32 arrays, an engine version).
- The two exceptions to statelessness. The quiz pairs in memory were designed in, so the page never holds a block id before
  the reveal. The memo of the last built session came with K38 and removes only the arrays request's second build, load
  still builds twice because `blocks` builds its own session (K39) and the real fix is an engine signature.
- Layering cost: pages broke until their tasks (F1's bridge edits redone by F2 and F3, e2e specs failing until S2), the
  block format had to move to `utilities/blocks.py` because accesses may not import each other, `schemas.py` is a named
  exception, and every layer went critical in turn, which is the 0.73.

### The work
- 97 commits on the branch, 64 for the rebuild: 1 docs, 20 real slice (12 backend, 7 frontend and tests, 1 notes), 33 K
  round, 7 synthetic first pass, 3 after. About 23,300 lines under `ratreplay/`. Sonnet built, Opus reviewed, the main
  session applied the should-fixes and committed, one commit per task, Kyle ran everything on real data.
- 26 of 29 tasks ticked (27 planned plus F6 and S3, open are K, R2 and D). K findings: 39, 31 fixed, 8 open. K21, K24, K31
  and K37 wait for Kyle, K18 is built and waits for his yaml, K29 is a follow-up, K39 a small task, and K20 looks built
  (07d46c1) but is unticked. Tests at the end: backend 229 (144 at the real slice), Vitest 193 (83), four Playwright flows
  (3), 170 project tests before R2, 85 after it removed the old tools and their tests.

### Issues to avoid
- A builder calling `create_app()` with the real config reads `configs/local.yaml` and the real folders. Builders use the
  synthetic fixtures and `serve_synthetic.py`, and `/bin/rm` and `/bin/cp`, the aliases hang.
- Commit chains passed failures until they ran under `set -o pipefail` with a grep for "failed", two early commits went
  through.
- The stale API. Builders write `dist/`, which Kyle's API serves, so he sees uncommitted work, and after a backend commit
  the process is old. Say "restart the API" in the handoff.
- Registration on synthetic data. A generator change that moves the corridor occupancy trips the real registration (37
  percent between the scales, K36). Check 20 seeds at 10 and 20 minutes before accepting a version.
- The quiz tells. Anything that differs by source gives the sides away: ids, runs, `t`, the environment backdrop. Two
  remain, a real block's lost heading (NaN) and the block length.
- Arena pauses. The labels paint none in the arena, so a pause there is a still stretch, and a still rat's speed noise under
  2 mm of tracking noise (0.02 m/s) rarely stays under the 0.03 floor for a second: 0 pauses a minute against 2.

### Recurring problems
- The synthetic data never matched in one pass: K35, K36, K37 (open). After version 3 the heading spread reads 1.4 times the
  recipe, the track turn rate 1.7 times, speed q25 23 percent low. Each fix moved the mismatch: version 2's wider wander
  flattened the corridor peaks, and version 3 repaired that for a narrow wander only (axis warnings in 20 seeds at 10 and 20
  minutes: 11 and 15 before, 2 and 0 after, 11 and 16 at real width).
- The page saying nothing or the wrong thing, six times: K2 (excluded read as an error), K17 (a failed load half disabled),
  K26 (an error on the next page), K32 ("changes nothing"), K34 ("kept as edited" read as unfinished, twice), K38 (a slow
  tunnel with nothing shown).
- What drawing tests cannot see: K1 (the occupancy image mirrored, the projection test passed), K17, K27 and K29 (colours
  against amber), K28 (a card clipped 18 px at 900 px). Vitest covers pure modules and the Playwright flows check steps at
  1440 by 900, not pixels.
- Science decisions arriving as findings (K5, K18, K28, K21, K31, K37). They change what enters the dataset or how it is
  registered, so they wait for Kyle, and 4 of the 8 open items are these.

### Commitment to quality
- Review and tests caught what they were aimed at: four documented divergences from the old edit rules (E2), the `rules`
  parameter windows needed (E4), a save on an unknown session returning 500 (S1), the block format shared across accesses,
  and in the synthetic review `t` leaking through the quiz and the environment backdrop.
- Kyle caught what they were not aimed at, 39 findings and almost all his: a mirrored map, a start site on the wrong side of
  a corridor (K18), a short tracking loss that drops a block (K31), words that read as unfinished, a generator that looked
  synthetic (K35, K36), a slow tunnel. No test caught any of them before he saw it.
- For the next slice: put Kyle's use first and small, one session through the new page before the next task. Give the
  generator an acceptance check before the quiz (the recipe round trip and 20 seeds of registration). Run one rendered check
  per canvas. Keep the science decisions in a list Kyle answers, and plan the first use round at about 1.8 times the slice.
