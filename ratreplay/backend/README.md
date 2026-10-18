# RatReplay backend

This file describes the old API and is rewritten in task R1, see [../docs/architecture.md](../docs/architecture.md) for the current design.

FastAPI on 127.0.0.1, one process, no database, the files are the state. The layering and the rules it follows are in
[../docs/architecture.md](../docs/architecture.md). This file is the API as built, the contract a client builds against.
`GET /api/openapi.json` is FastAPI's schema of the same routes and `GET /api/format` is the data format.

    pixi run ratreplay-api           # http://127.0.0.1:8060
    pixi run python -m pytest ratreplay/backend/tests

Errors leave as `{"error": text}`: 404 for an unknown session, block or file and for a transformed folder that is not
there, 400 for a request that cannot be served (a key the config lacks, a review with a block still auto), 422 for a body
or query that fails its schema, the text naming the field.

## Sources

The two data folders are the ones the processor reads, `TRANSFORMED_LAB_DATA` and `PROCESSED_LAB_DATA` in
`configs/local.yaml` (read through the `utilities.config` utility), each resolved with `expanduser().resolve()`. Only
`DataSources` (`stores/data_sources.py`) knows the two keys and the file. The app builds one at start, it reads the file
then and again on reload, the managers hand it to the stores, which ask it for their folder. It refuses with the 400 and
404 below. `create_app(config_path, settings_path)` takes other files instead, which is how the tests
and the Playwright server name their synthetic folders and never touch the real ones. No route takes an id for a folder:
the session routes read the transformed folder, the block and settings routes the processed folder, and the reviews live
under its `review/`.

    GET /api/sources
    GET /api/sources?reload=true      reads the config file again first

The answer is `{transformed, processed, config_path}`, `config_path` being the file the folders come from. Each folder
is `{path, status, problems, counts, manifest}`. `status` is `ok` or `invalid` with `problems` listing what breaks the
format (empty when ok), checked at each request. A key the config lacks gives `path` null, `invalid` and the problem
`TRANSFORMED_LAB_DATA is not set in <config_path>`, and the routes that need the folder answer 400 with that text. `counts`
holds `sessions`, `epochs`, `runs` and `frames` (transformed) or `blocks` and `reviews` (processed). `manifest` is null
or `{timestamp, modified}`, the run timestamp of the folder's manifest and when its newest file was written. A processed
folder the processor has not run in yet is `ok` with a null manifest and no `blocks` count, since the first review save
creates it. A transformed folder that is not there is `invalid` with the problem `TRANSFORMED_LAB_DATA <path> does not exist`, and its routes answer 404 with that text.

## Sessions

    GET /api/sessions
    GET /api/sessions/{session_id}
    GET /api/sessions/{session_id}/arrays

The index is a list of rows: the sessions.csv columns, `epochs`, `n_runs`, `n_clean_runs`, `in_dataset` (the session
survives the processor's funnel), `n_automatic` (the blocks the processor would build, null when there is no frames
file), then `reviewed`, `reviewed_at`, `reviewed_by`, `n_confirmed`, `confirmed_s` (seconds per epoch kind) and `notes`.
Dataset sessions come first, then unreviewed ones, then the oldest review first.

A session is two requests. The header is json: `session_id, subject_id, date, protocol, group, rate_hz, max_gap,
n_frames`, `epochs`, `block_epochs` (the epochs the processor cuts into blocks), `runs`, `cuts` (`pauses` and `jumps` as frame numbers, `gaps` and `margins` as [first, last]
pairs), `heading_lost`, `heading_filled`, `heading_held` (lists of [first, last] lab frames), `led_offset` (`rad`, `r`),
`occupancy` (`bins`, the `x` and `y` extent and, by epoch name, the counts row by row from the lowest y, bins squared
values) and `blocks`, the automatic blocks. The arrays are an Arrow IPC stream (`application/vnd.apache.arrow.stream`),
one row per frame in frame order, frame number is the row index plus one: `t` s, `x` and `y` px (the mashup light),
`heading` rad (filled and corrected by the LED offset), `speed` px/s, `motion` rad (direction of motion, camera axes),
`n_lights` int8. NaN is NaN, never null.

## Reviews

    GET  /api/sessions/{session_id}/review                the review file or null
    PUT  /api/sessions/{session_id}/review                {"edits": [...], "notes": ""}
    POST /api/sessions/{session_id}/review/preview        {"edits": [...]}

An edit is `{"op", ...}`. The ops and their fields are `accept`, `confirm {frame}`, `move {frame, edge, at}`,
`split {frame}`, `drop {frame}`, `new {frame_start, frame_end}`, `cut {frame_start, frame_end}` and `flag {run}`,
listed in `GET /api/format`. The server replays them on the automatic blocks with the processor's rules, so an edit that
no longer applies is skipped. An edit anchored at a frame (`confirm`, `move`, `split`, `drop`) reaches the block
holding it, a block that is not removed before one that is, so a new block over a removed one is the one reached, and
the removed one only by a frame the new block leaves out. A removed block does not come back over a block that is kept:
a `drop`, `move`, `split` or `cut` that would bring it back while a kept block overlaps it is skipped, so a saved review
never holds two kept blocks that share a frame. The blocks come in frame order, two that start on one frame in the order
they were made, which is how the old tool numbers them. PUT writes `review/<session_id>.json` whole under the
processed folder and answers `{"review": <the file's content>, "path", "overwrote": bool}`. It is refused with 400 while
a block is still auto.
POST answers `{"blocks", "cuts", "flagged_runs", "skipped"}` and writes nothing: the blocks the edits make (with the
review file's block keys), the ranges cut, the runs flagged and the edits skipped, each with a `reason`: that no block
holds the frame it anchors to, the processor's refusal of a new block (it crosses a cut, lasts under the minimum or
overlaps a kept block), or that a removed block cannot come back over a kept one. It is the way a client shows the result
of an edit, or the skipped count of a saved review, without reimplementing the rules.

## Blocks

    GET /api/blocks?{settings}
    GET /api/blocks/{block_id}?{settings}
    GET /api/blocks/{block_id}/arrays

`{settings}` are the window settings as query parameters, the project's defaults where one is left out: `window_s`,
`stride_s`, `burn_in_s`, `horizon_s`, `train_rate_hz`, `min_heading_measured`, `min_complete_trips`. The index answers
`{"blocks", "totals", "settings"}`: each block is its blocks.csv row with `heading_measured` (share of frames),
`n_windows`, `ok` and `reason` at the settings, `totals` the blocks ok and in trouble, the windows and the hours per kind
and overall. A processed folder without a manifest answers 404.

A block header is json: the row's facts, `kind`, `status`, `environment`, `geometry` (`name, kind, room, boundary,
walls, centerline, reward_sites` in metres, and for a circle `circle {center, radius}`), `rate_hz`, `frame_start` (the
lab frame of the first row), `runs`, `trips` (spans with `partial`), `phases`, `heading_filled`, `heading_held`,
`one_light` (index pairs into the block), `verdict {ok, reason}`, `settings` and `windows`. Each window is `{index,
first, burn_in_stop, window_stop, stop, position_finite, heading_measured, trips_complete, trips_partial, ok}`: indices
into the block's arrays with the stops exclusive, `stop` the end of the window plus its horizon, the checks taken over
that whole range, `ok` when the position is finite throughout and the measured heading share reaches the minimum.
`trips_complete` counts the trips whose outbound start and return end both lie inside that range and `trips_partial` the
other trips touching it, cut by the range or by the block. The rows come from `axis_of_travel_rnn.windows.window_rows`,
like the verdicts, the totals and the settings file. The arrays are an Arrow
stream, one row per frame: `frame` (lab frame number), `t` s, `x` and `y` m, `heading` rad, `speed` m/s, `n_lights`.

## Window settings

    GET /api/windows/settings
    PUT /api/windows/settings    {"settings": {...}}

Both answer `{"settings", "saved", "path"}`: the settings in force (the saved ones, else the defaults), the settings file
as saved (`settings, processed_manifest_timestamp, rules, totals, written_at`) or null, and where it lives. PUT writes
the file whole with the processed folder's manifest and the totals over its blocks, and also answers `overwrote`.

## Format

    GET /api/format

The contract: for `transformed` and `processed` the files with their columns (name, type, `required` when the tool reads
it), for `review` the keys, block keys, statuses and edit fields, and the default `window_settings`.

## Differences from the old tool

`src/ratreplay` still runs and reads and writes the same review files and settings file. The backend no longer imports
it: the edit rules are copied into `ratreplay_api/engines/edits.py`. `tests/test_parity.py` runs the same edits through
both and finds the same review files, session facts and arrays, except for these two, which it documents:

- An edit anchored at a frame where a new block lies over a removed one reaches the new block here, and the removed one
  in the old tool, where the removed block comes first in its list.
- A removed block does not come back over a kept one. The old tool accepts the `drop`, `move`, `split` or `cut` that does
  it and saves two kept blocks over the same frames, which the processor then fails both of on its `one_block` check.
  Here the edit is skipped with the reason named, in a preview and in a saved review.
