# RatReplay backend

FastAPI on 127.0.0.1, one process, no database, the files are the state. The layering and the rules it follows are in
[../docs/architecture.md](../docs/architecture.md). This file is the API as built, the contract a client builds against.
`GET /api/openapi.json` is FastAPI's schema of the same routes and `GET /api/format` is the data format.

    pixi run ratreplay-api           # http://127.0.0.1:8060
    pixi run ratreplay-test          # the backend tests, then the frontend's

The folders come from `TRANSFORMED_LAB_DATA`, `PROCESSED_LAB_DATA` and `SYNTHETIC_DATA` in `configs/local.yaml`, read at start
and again on `GET /api/health?reload=true`. `create_app(config_path)` takes another file, which is how the tests name synthetic folders.

Window settings are seven fields: `window_s` 40, `stride_s` 10, `burn_in_s` 1, `horizon_s` 0.5, `rate_hz` 20,
`min_heading_measured` 0.8 and `min_complete_trips` 1, the defaults where one is left out and any other key a 422.
On a GET they are query parameters, elsewhere the body's `settings` object (optional on preview, save and exclusion).

## Routes

| Route | Query or body | Answer |
| --- | --- | --- |
| `GET /api/health` | `reload=true` | `transformed`, `processed`, `synthetic`, `environments`, each `root, exists, problems, counts, manifest`, and `config_path` |
| `GET /api/format` | | `version`, `transformed`, `processed` and `synthetic` (files, columns, keys), `settings` (the defaults) and `rules` (the engine's rules and their values) |
| `GET /api/environments` | | one entry per environment of `configs/environments`, `name, kind, params, geometry, sessions, summary`. `sessions` are the built sessions registered in it, per epoch kind `session_id, kind, scale_px_per_m, led_separation_m, rotation_rad, flip, offset_m` (and `scale_x, scale_y, start_offset_measured_m` on a track, the last missing from a build made before it was recorded), `led_offset_rad, led_offset_r, led_offset_n, warnings, built_at`. `summary` is `n_sessions, n_warned`. Read only |
| `GET /api/sessions` | | rows of the sessions.csv columns plus `epochs, n_runs, n_clean_runs, in_dataset, reason, annotated_exclude, built, reviewed, reviewed_at, reviewed_by, excluded, excluded_by, excluded_at, n_confirmed, confirmed_s, notes` |
| `GET /api/sessions/{sid}` | settings, `start_offset_m` (optional) | the session's facts, `n_frames, in_dataset, reason, annotated_exclude, excluded, epochs, runs, selected_epochs, n_initial_blocks, environments, frame, heading_spans, cut_points, margins, stretches, occupancy, stops, warnings, start_offset_m, start_offset_default_m, review, blocks, refusals, cuts, flagged_runs`. The environments are built with the start offset that applies, the query's when given, else the saved review's, else the yaml's: `start_offset_m` is that value (none for the yaml's) and `start_offset_default_m` the yaml's (0.0 when unset). `frame.track.start_offset_measured_m` is the offset measured from the session's own occupancy |
| `GET /api/sessions/{sid}/arrays` | `start_offset_m` (optional) | Arrow: `t, x, y, heading, speed, turn_rate, motion, n_lights`, registered with the same start offset as the header |
| `POST /api/sessions/{sid}/preview` | `{edits, settings, start_offset_m}` | `blocks, refusals, cuts, flagged_runs`, nothing written. `start_offset_m` is required in the body and used as given, null being the yaml's and not the review's |
| `PUT /api/sessions/{sid}/blocks` | `{edits, notes, settings, start_offset_m}` | `review, replaced, file, built, failed, build_error`. `start_offset_m` is required and written into the review exactly as given, so null clears a saved offset back to the yaml's. The build's metadata records it |
| `PUT /api/sessions/{sid}/exclusion` | `{excluded, note, settings}` | `review, replaced, file, deleted, built, failed, build_error`. The review is rewritten (or written from the initial blocks) with `excluded`, `excluded_by`, `excluded_at` and the note appended, `reviewed_by` and `reviewed_at` untouched. Excluding builds the session empty at once. Including writes the review only, or removes it (`review` none, `deleted` true) with the session's build when it was only the exclusion's |
| `POST /api/rebuild` | `{settings}` | `sessions` (each `built, failed, build_error`, an excluded one builds nothing), `skipped` (reviews of sessions the funnel leaves out, with the reason), `excluded` (notes by session id) and `totals` (`sessions, built, failed, errors, skipped, excluded`) |
| `GET /api/blocks` | settings, `which=real` or `which=set:{id}` | `which, settings, blocks, totals, built` |
| `GET /api/blocks/{bid}` | | `row, rate_hz, geometry, runs, trips, phases, heading_filled, heading_held, one_light`, a real block or one of a synthetic set |
| `GET /api/blocks/{bid}/arrays` | | Arrow: `frame, t, x, y, heading, speed, turn_rate, n_lights, trip` |
| `GET /api/blocks/{bid}/windows` | settings | `rows, verdict, count` |
| `GET /api/windows` | | `{"selected": null}` or `selected` holding `settings, totals, selected_at, selected_by` |
| `PUT /api/windows` | `{settings}` | `replaced, file`, writes `windows.json` whole |
| `GET /api/sets` | | one row per synthetic set: `set_id, created_at, created_by, sources, seed, length_s, n_blocks, kinds, n_guesses, n_correct` |
| `POST /api/sets` | `{sources, seed, length_s, settings}` | `set_id, built, failed, warnings, kinds`. `sources` are built session ids, `length_s` the seconds per kind (`arena`, `track`), the set is written whole with its provenance |
| `GET /api/sets/{id}` | | the provenance (`set_id, created_at, created_by, sources, environments, camera, seed, length_s, rules, settings, code_version, generator, recipe_real, recipe_synthetic, warnings, failed`) and `blocks`, its blocks.csv rows |
| `DELETE /api/sets/{id}` | | `deleted, blocks`, the set's folder and its open pairs gone |
| `POST /api/sets/{id}/pairs` | `{kind}` (null for any) | `pair_id, kind, sides`: one real block of the set's sources and one synthetic block of the kind, the real one on a side drawn at random, kept in memory until the guess |
| `GET /api/pairs/{pair_id}/{side}` | | `row` (`kind, environment, n_frames, duration_s, rate_hz` only), `rate_hz`, `geometry`: what the quiz player draws and nothing that would tell the block's source (no ids, runs, trips, phases, fills, lights or registration) |
| `GET /api/pairs/{pair_id}/{side}/arrays` | | Arrow: `t, x, y, heading, speed` |
| `POST /api/sets/{id}/guesses` | `{pair_id, side}` | `correct, real_side, real_block, synthetic_block, tally`, the guess appended to the set's `guesses.json` and the pair closed |
| `GET /api/sets/{id}/guesses` | | `tally` (`n, correct, by` per user `n, correct`) and `guesses` (`at, by, pair_id, real_block, synthetic_block, kind, guessed_real, correct`) |

What the answers hold, beyond their keys:

- An edit is `{"op", ...}` with the fields `GET /api/format` lists under the review's edits: `accept`, `confirm {frame}`,
  `move {frame, edge, at}`, `split {frame}`, `drop {frame}`, `new {frame_start, frame_end}`, `cut {frame_start,
  frame_end}`, `trips` (no fields, one block per complete trip of the track in place of the kept track blocks) and `flag {run}`.
  Frames and runs are whole numbers from 1.
- A block of the session header or a preview is `block_id, epoch, environment, frame_start, frame_end, status, note`,
  plus `windows` (`count`, `verdict`, null for a dropped block) and `problems`. `refusals` are `{index, op, reason}`.
- Save applies the edits first and one illegal edit refuses the whole save. It also refuses a kept block not yet accepted (still auto or edited) and a
  session the rules leave out (400), writing nothing. Once the review is written, a failed build comes back as
  `build_error` with the review kept, and `failed` lists the blocks with problems, which are not written.
- A readiness block is its blocks.csv row with `count` and `verdict {ok, reasons}`, judged under the rules its session
  was built with (for a synthetic set, the rules in its provenance). `totals` are `blocks, ok, trouble, windows, windows_ok`.
  `built` gives per built session (or for the set, under its id) the `settings`, `built_at`, `excluded` and the `failed`
  blocks with their problems. A `which` that is neither `real` nor `set:{id}` is a 400, a set that is not there a 404.
  A window row is `index, first, burn_in_stop, window_stop, stop, start_s, stop_s, position_finite,
  heading_measured, trips_complete, trips_partial, ok, reason`, where `first` and the three stops are indices into the
  block's arrays, the stops exclusive.
- Select refuses with 400 while nothing is built. Rebuild builds only the sessions with a review.
- Generate refuses with 400 a source with no built blocks, a kind in `length_s` the sources have no blocks of, a track
  that is not the triple T, an arena that is not a circle, and a track recipe with no outbound runs or no dwells to draw
  from, nothing written. The set id is `syn_{YYYYMMDD}_{HHMMSS}_{seed}`, its blocks `{set_id}_{kind}_{n}`, so `GET /api/blocks/{bid}`
  finds a synthetic block when the processed folder lacks the id. A pair lives in the API's memory until it is guessed, the
  set is deleted or the API restarts, after which its routes are 404. A guess names a pair of another set with 400.

Errors leave as `{"error": text}`: 404 for an unknown session, block, set, pair or route and for a transformed folder that
is not there, 400 for a request that cannot be served (a config key that is not set, an illegal edit, a session out of the
dataset, nothing built to select), 422 for a body or query that fails its schema, the text naming the first field.

The three `/arrays` routes answer an Arrow IPC stream (`application/vnd.apache.arrow.stream`), one row per frame, each
column in its own dtype and NaN kept as NaN. Positions are in metres.

## Layout, `ratreplay_api/`

    app.py          composition root: config read, components built once and again on reload, routes, frontend at /
    schemas.py      the request bodies and the settings query, unknown keys refused
    routers/        review.py, synthesis.py and validation.py, the HTTP face of each manager, no logic
    managers/       ReviewManager, SynthesisManager and ValidationManager, the workflows
    engines/        trajectory/ (TrajectoryEngine, pure functions over arrays) and generator.py (GeneratorEngine)
    access/         transformed.py, processed.py, synthetic.py, environment.py, one per resource with its schema inside
    utilities/      config, tables, files, blocks (the block format both block folders share), arrow, clock, paths, spans, version, errors
    tests/          unit/ (engines, accesses, import layering), integration/ (one file per manager), system/ (HTTP)
