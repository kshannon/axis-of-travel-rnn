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
- [x] A4 `access/synthetic.py`, SyntheticAccess over `sets/{set_id}/` (blocks.csv and blocks parquet in
      the processed schemas, provenance.json, guesses.json): health, sets, set, blocks, block, write_set,
      delete_set, guesses, write_guess. Test: write then list then delete, provenance round trips, a
      guess appends. [Accesses, plan: Synthetic slice design]

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
- [x] E5 `recipe(blocks, rules)` in `engines/trajectory/recipe.py`: per kind the statistics the plan lists
      (speed, turn rate, still fraction, heading spread, pauses, track runs, dwells, trips, goal shares,
      phase shares, arena boundary distance and occupancy grid, counts). Test: the recipe of a fixture
      block equals hand computed numbers, an empty kind gives counts of zero. [TrajectoryEngine, plan]
- [x] E6 `engines/generator.py`, GeneratorEngine.session(recipe, environments, camera, seed, length_s)
      in the transformed schema as the plan says (trips over the centreline graph, the arena walk, two
      LEDs in camera pixels, the runs table). Test: same seed same arrays, the result passes
      TrajectoryEngine.blocks and labels every run, the walk stays inside the corridors and the circle,
      the run durations and speeds sit within the recipe's quantiles. [GeneratorEngine, plan]

## Managers and routers

- [x] M1 `managers/review.py`, ReviewManager (index, load, preview, save_blocks, rebuild_all) and
      `routers/review.py`. Integration test: load, preview a refusal, save, load again gets the blocks back,
      rebuild all rebuilds two sessions, an illegal edit refuses the whole save. [ReviewManager, API]
- [x] M2 `managers/validation.py`, ValidationManager (health, format, readiness, block, windows,
      select_settings) and `routers/validation.py`. Integration test: health names the problem, readiness
      on real and on a set, select writes windows.json whole. [ValidationManager, API]
- [x] M3 `managers/synthesis.py`, SynthesisManager (index, generate, delete_set, pair, guess, tally) and
      `routers/synthesis.py`, `SYNTHETIC_DATA` wired in app.py and health, ValidationManager reading a
      set's blocks for readiness `set:{id}`, block and arrays. Integration test: generate from two source
      sessions writes a set with its provenance and both recipes, a pair then a guess records it and the
      tally counts it, delete removes the set. System test: the routes. [SynthesisManager, API, plan]
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
- [x] F4 Synthetic page between Windows and Outgoing: the sets with their provenance, Generate (source
      sessions from the built ones, seed, minutes per kind), Delete with confirmation, the real and
      synthetic recipes side by side per kind for the chosen set, the synthetic folder on Incoming's
      read from and on Outgoing. The Blocks page's dataset choice lists the sets. [Page 6, plan]
- [x] F6 Real or synthetic page after Synthetic: choose a set, New pair, two block views side by side
      (map trail with playback, speed trace, no ids, runs or paths), Left is real or Right is real, the
      reveal, the set's tally. [Page 7, plan]
- [x] S3 `serve_synthetic.py` gains the synthetic folder and a Playwright flow: generate a set from the
      built sessions, see its comparison, answer one pair, delete the set. [Testing]
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
- [x] R2 remove `src/process_lab_data`, the `process-lab-data` task, old `src/ratreplay`, the parity
      tests that import them, `configs/datasets/lab_blocks.yaml`. Check: `pixi run test` green. Then add
      `start_offset_m` to `REVIEW_KEYS` and `METADATA_KEYS` in processed.py so the format page lists it.
      [Migration]
      Done: old tools, their tests, plotly and dash removed, fixtures build through ReviewManager, keys added.
      `lab_blocks.yaml` stays, it is the CONFIG of `axis_of_travel_rnn.windows`.
- [x] D debrief appended to `plan.md`: estimation accuracy, design efficacy, the work, issues to avoid,
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
- [x] K17 Replay visuals, second pass: the button groups readable in both themes, the layer toggles plain
      light bordered boxes with the colour dot after the word, tracking lost a striped coloured bar, the
      speed line lighter, the faint grid lines removed, "recording paused" gone as a toggle and pauses
      drawn as dead time (a break in every lane, no span bridges a pause), and a failed session load
      reported in the warning stack with the page left usable, never silently half disabled. Kyle,
      2026-10-18. [Page 3]
- [ ] K18 Triple T start offset: Olson 2017 Figure 1 shows the start site up the stem above a bottom
      return corridor, our yaml put the start on the bottom edge, so the registration anchors the data
      too low (the bottom corridor spills under the outline, the y scale warning follows). Add a
      `start_offset` parameter to the triple_t builder (both copies until R2), measured from a session's
      own occupancy on the Environments page (distance from the start anchor to the bottom corridor
      centreline, in metres), set it in the yaml, Rebuild all re-registers. Kyle, 2026-10-18.
      Built: the parameter in both builders and the measurement on the Environments page, open until
      Kyle sets the yaml from his sessions (steps in plan.md).
      [EnvironmentAccess, Page 7, configs/environments]
- [x] K19 Replay session picker in the status header: the session id becomes a searchable drop down of
      the index (filter by id or rat, dataset sessions first, reviewed and excluded marked) with previous
      and next arrows beside it that follow the index order, unsaved edits asked about before leaving.
      Kyle, 2026-10-18. [Page 3]
- [ ] K20 A new block or a mark inside an epoch the rules do not cut (a variant under another condition)
      is refused with the real reason, "this epoch is variant under condition rot45, the rules cut blocks
      only from arena and track under baseline", not the between two cuts message, and the session lane
      marks such an epoch as not cut. Kyle, 2026-10-18. [TrajectoryEngine.apply, Page 3]
- [ ] K21 Proposed, awaiting Kyle: head direction is not interpolated across frames whose position is
      missing (a tracking loss inside a heading gap), it stays missing there, so an interpolated span
      splits around the loss as the timeline suggests it should. Changes the heading column of blocks on
      frames the window checks already reject for position. [TrajectoryEngine.session heading fill]
- [x] K22 Playback: the speed slider becomes a labelled stepper ("speed 1x", minus and plus over the
      steps), and the keyboard hints (space, z, enter) become key caps with a title saying what the key
      does, so neither reads as a button or a progress bar. Kyle, 2026-10-18. [Page 3]
- [x] K23 Timeline span tips explain the rule: hovering a heading span shows its length and why it is
      what it is ("4.1 s missing, over the 3 s fill limit", "touches a pause", "2.0 s interpolated",
      "0.8 s held, the rat was still"), the engine returning the reason per span so the client states
      nothing of its own. Kyle, 2026-10-18. [TrajectoryEngine.session heading spans, Page 3]
- [ ] K24 Proposed, awaiting Kyle: the block card layout. Facts as a chip row (kind, length, runs,
      trips), the window count large, the heading shares as a thin four colour bar (measured,
      interpolated, held, missing, seconds on hover) from the engine's per block numbers handed through
      the manager (the client stops summing spans), the verdict reasons one per line with a mark, the
      same card on the Blocks page. [Pages 3 and 4, ReviewManager]
- [x] K25 Map controls as two groups: layer checkboxes (occupancy, geometry, trail) and one radio for the
      epoch scope (follow the cursor, arena, track, both), the map title naming what is shown. Kyle,
      2026-10-18. [Page 3]
- [x] K26 A page loads its data when it is shown, not at boot: the Replay page's remembered session was
      loading while Incoming was on screen and its error surfaced there. Kyle, 2026-10-18. [Frontend]
      Found: the shell already mounts one page at a time, the leak was a load still in flight when the
      person left, which toasted on whatever page came next. Each page now holds a Visit and says nothing
      after it is hidden, Replay keeps its session for the next visit to retry.
- [x] K27 Dark theme restyled toward Monokai: warm dark greys for the page, card and lines (not near
      black), silver text, amber and an 80s sci fi yellow as the accent and the attention colour, the ok
      green and the problem orange tuned to that family, the timeline and map colours checked against the
      new ground. Reference: the Alien Romulus poster duotone, amber yellow #F2A900 to #FFC233 as the accent,
      burnt red orange #D9442B for a problem, warm charcoal ground with a hint of brown, cream text. Second reference, the Nostromo cockpit: warm dark brown ground, brass and ochre
      panel surfaces for cards and strips, amber indicator lights for the status marks, CRT phosphor green
      for ok and for data on a dark panel, red only where something is wrong. The speed colouring of the trail and its legend use the magma
      scale (or its yellow end) instead of viridis, which also fits the light theme. The light theme stays. Kyle, 2026-10-18. [UX rules]
      Built: page #1c1814, card #26201a, ink cream #f1e6cf, accent #f2a900, warn #ffc233, ok #7ed957, bad
      #e65c33 (the poster's #D9442B reads under 4.5:1 on the card), track bronze, return runs sand, cursor
      violet kept. Magma trail in both themes (dark uses 0.35 to 1, light 0 to 0.8). Lane labels switch to
      the page colour on a bar the cream cannot be read on. Left open: accent and warn sit close, so the
      flag outline on an amber run is faint, and the Replay help text still names the light theme's blues.
      [K29 below]
- [ ] K31 Proposed, awaiting Kyle: a block failed its build with "position not finite on 12 frames"
      (NS14_rec5_20141201_001_track_02). The gap rule cuts only a loss of both lights longer than the
      session's max_gap (30 frames, the lab's own interpolation limit), a shorter loss stays inside the
      block with NaN positions, the processor's check refuses it and the build drops it. The timeline
      does not show such a loss either, the tracking lost layer draws only the gaps the rule cut. Options:
      (a) fill position linearly over a loss of max_gap frames or less, as the lab meant to, with a
      position_filled column and a layer on the timeline, (b) cut at any loss of both lights, more and
      shorter blocks, (c) keep dropping and draw short losses so the person cuts them by hand. In every
      case the short losses get drawn. [TrajectoryEngine.session, build, Page 3]
- [x] K32 An edited block is already kept, and the page must say so instead of "That changes nothing":
      the card's Accept on an edited or removed block looks enabled though it is not (the chips have no
      disabled look), the timeline's Accept on an edited block sends a confirm the engine ignores and the
      toast says nothing useful. The card shows "kept as edited" in place of Accept, the timeline's Accept
      is disabled with the reason, a refused or empty edit names its reason, and a block problem says its
      consequence: "not built until this is cut out or the block rejected". Kyle, 2026-10-18. [Page 3]
- [x] K33 A "Cut marks out" button: the engine's cut edit (a range removed from every block it touches, a
      piece under min_block_s dropped with its note, never refused for length) has no button, so the only
      way to remove 12 bad frames from the middle of a block was two splits, and the second is refused with
      "a kept block must last 10 s or more". The button joins the marks group, acts on the marked range,
      the refusal says to cut the range out instead, the guide says when to split and when to cut. Kyle,
      2026-10-18. [Page 3, TrajectoryEngine.apply message]
- [x] K34 Every kept block is confirmed by the person: Accept turns an automatic or an edited block
      confirmed (Accept all too), Accept on a confirmed block does nothing (Undo takes a mistake back),
      and Save requires every kept block to be confirmed, so "edited" is a passing state, changed but not
      yet approved. The edit list keeps the history. The engine version bumps, since apply answers
      differently for the same input. Kyle, 2026-10-18, after twice reading "kept as edited" as unfinished.
      [TrajectoryEngine.apply, ReviewManager.save_blocks, Page 3]
      Built: engine version 2. A review saved before it that holds edited blocks shows "saved blocks
      differ" when opened, Accept all and Save brings it up to date.
- [x] K35 Generator version 2, after Kyle's first quiz on real data: the synthetic rat hugs one line, takes
      square corners, sits still at the sites, runs identical bells and has no tracking noise, the real one
      fills the corridor, cuts corners, wanders at the goals, varies its pace within and between runs and
      jitters frame to frame. The recipe measures three more things on the real blocks (the lateral
      distance from the centreline on the track, the within run speed variation, the tracking noise as the
      spread of the position's second difference) and the generator matches them: lateral wander with the
      measured spread on two time scales, corners rounded by smoothing the path over a quarter second,
      a per run pace multiplier and a slow within run modulation, dwells as a local wander with still
      stretches, per LED pixel noise, and now and then an excursion between trips that is not a run.
      Heading from Kyle's analysis of the 109 sessions: the head points backwards in the synthetic at small
      steps and barely moves when still, while the real head minus travel scatter falls with speed (about
      145 degrees at 0.05 m/s down to 15 at 0.67 on the maze, a 50 degree floor in the arena) and the head
      lags the travel direction by about 44 ms on the maze and 149 ms in the arena. The recipe measures the
      spread per speed bin and the lag, the generator builds heading as the smoothed travel direction
      delayed by the lag plus an AR(1) noise with the speed's spread, so the head sweeps while still and
      settles while running. Provenance generator version 2. Kyle, 2026-10-19. [TrajectoryEngine.recipe,
      GeneratorEngine, plan]
- [x] K36 After Kyle's second quiz on real data, generator version 3: the synthetic session tripped the
      registration ("track scale x and y differ by 37 percent, an outer corridor peak missed") so its
      trail drew out of proportion to the maze, since a symmetric wander about the centreline spreads the
      outer corridor peaks flat while a real rat hugs the outer wall on the perimeter. The recipe measures
      the signed lateral offset, outward positive, on perimeter and on inner segments, and the generator
      applies it. Real rats also dwell longer and go back and forth: the recipe measures reversals per
      minute (the direction of travel turning by over 120 degrees while running) and the generator makes
      them, and the dwell draw is checked against the real dwell quantiles. Verified over 20 seeds at 10
      and 20 minutes with no axis warning. Kyle, 2026-10-20. [TrajectoryEngine.recipe, GeneratorEngine]
      Built as version 3, the registration target met on the test recipe only: with a real width of
      wander (3 cm) the axis warning still fires on about half the seeds at 20 minutes, the top corridor
      peak falling under the prominence cutoff set by the approach row. Open as K37.
- [ ] K37 Proposed, awaiting Kyle: the registration on a synthetic session of real width. Options: the
      dwell moves kept under the running threshold so the goal row stops dominating the running histogram,
      frames within 0.15 m of a reward site left out of the scale histogram (a change to real data
      registration too), or the prominence rule lowered. The next real generate at 20 minutes says
      whether the real recipe trips it. [TrajectoryEngine.session frame]
- [x] K38 Opening a session over a tunnel is slow and silent: the header request builds the whole session
      and the arrays request builds it again, ten float64 columns travel as Arrow, and the page shows
      nothing until both land. ReviewManager keeps the last built session (keyed by session id, start
      offset and the transformed stamp) so the second request reuses it, the arrays travel as float32
      except t, and the Replay page says "loading {sid}, {n} s" in the session card and the map while it
      waits, with the health store retried on the Incoming page when the boot read failed. Kyle,
      2026-10-20. [ReviewManager, Page 3, Frontend]
      Built: on the fixture session the arrays request fell from 8 ms to 0.1 ms and the stream shrank 44
      percent. Left: load still builds the engine session twice, since blocks builds its own inside the
      manager's _made, about half of load's time, K39.
- [ ] K39 TrajectoryEngine.blocks takes a built session (or the manager hands it the one it has) so a
      header load builds the session once. [TrajectoryEngine, ReviewManager]
- [x] K40 Blocks for training are cut by hand, so two helps. The edit "trips" (no fields) replaces the kept
      track blocks with one block per complete trip: an outbound run (path in outbound_paths) to the end of the
      first return run (path in return_paths) that starts before the next outbound run, both inside one stretch
      (no cut, pause or gap inside), else the trip is skipped. The old track blocks are removed with the note
      "replaced by one block per trip", a trip block is edited, a trip under min_block_s is removed with the short
      note so a save is never refused for it, the arena blocks stay. A button "One block per trip" sits beside
      Accept all and its toast counts the trip blocks made and dropped. The keys A and R accept and reject the
      selected block as the buttons do, with the button's reason as a warning when they cannot, and do nothing
      while the person types in a field. Kyle, 2026-10-21. [TrajectoryEngine.apply, Page 3]
      Built: the engine version stays 2 (no old input answers differently), the format version stays 4 (an
      added op). Left: a run flagged as wrong still makes a trip, since flags only act when the blocks are built.
- [ ] K29 Dark theme follow-ups: a flag outline and an edited block that read against amber (another
      hue or a thicker stroke, not alpha alone), the Replay and Blocks help text naming colours by token
      word (outbound, return, flagged) instead of blue and violet. [Page 3, Page 4]
- [x] K30 The seven frame layers (tracking lost, position jumped, margins trimmed, head dir missing,
      head dir interpolated, head dir held, speed) each get their own colour token in both themes, no
      two alike and none borrowed from accent, bad, soft or trip, so a layer is told from the others and
      from the trips and blocks at a glance. Kyle, 2026-10-18. [UX rules, Page 3, Page 4]
      Built: tokens lost, jumped, trimmed, hd-missing, hd-filled, hd-held, speed in both themes, margin
      removed. Dark: violet, pink, cool grey, orange red, amber, cyan, cream. Light: magenta violet, pink,
      dark grey, orange red, blue, teal, ink. Tests: 3:1 on the card and 15 or more CIE76 between every
      pair. Checked by CIEDE2000 and under deuteranopia and protanopia, three fixes applied (light trimmed
      a neutral grey #686868 parting from held by lightness, light lost a deep magenta #79007c parting
      from the accent blue for deuteranopes, dark trimmed #6f6c68 cooled away from trip). Left: dark
      jumped against trimmed is 9 under protanopia, a thin tick against a band. Kept by choice:
      hd-filled is the accent by value (RatReplay's own work) and hd-missing is bad (a problem), and lost
      sits near the cursor in hue in both themes (a striped bar against a one pixel line). [K29 for the
      accent and warn closeness]
- [x] K28 The start offset is tuned per session on the Replay page and saved with the review: the real
      start sits up the stem, not at the bottom corridor, and by how much is the person's call per session
      while the yaml keeps the default. A small "Start offset, m" stepper under Flag run (the notes box
      shorter), a change re-registers the session through preview so the map and trail move, Save writes
      `start_offset_m` into the review (null means the yaml's), the metadata records it, a "Use measured"
      button fills in the engine's `start_offset_measured_m`. EnvironmentAccess builds the geometry with
      the override, the engine is untouched, FORMAT_VERSION goes to 3. Kyle, 2026-10-18. [EnvironmentAccess,
      ReviewManager, Page 3]
      Built: on the GETs the query's offset applies, else the review's, else the yaml's (a query cannot
      carry null), on preview and save the body field is required and used as given, so Default then
      Save writes null. The field moves the session 300 ms after typing stops, "not saved" shows while it
      differs from the saved one, Use measured hides without a track epoch and is disabled outside the
      field's range of plus or minus 0.5 m. An offset the maze cannot close around (0.33 m or more) is
      refused with the builder's message. The Playback card clips by 18 px at 900 px of height.
