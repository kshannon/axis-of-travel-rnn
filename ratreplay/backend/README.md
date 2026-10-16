# RatReplay backend

FastAPI on 127.0.0.1, one process, no database, the files are the state. The layering and the rules it follows are in
[../docs/architecture.md](../docs/architecture.md). This file is the API as built, the contract a client builds against.
`GET /api/openapi.json` is FastAPI's schema of the same routes and `GET /api/format` is the data format.

    pixi run ratreplay-api           # http://127.0.0.1:8060
    pixi run python -m pytest ratreplay/backend/tests

Errors leave as `{"error": text}`: 404 for an unknown source, session, block or file, 400 for a request that cannot be
served (a bad attach, a session route on a processed source, a review with a block still auto), 422 for a body or query
that fails its schema, the text naming the field.

## Sources

A source is a folder and a kind: `transformed` (the converter's tables and frames) or `processed` (the processor's blocks
and manifest). A transformed source is paired with the processed folder its reviews and blocks live in (it need not exist
yet, the first save creates `review/`), a processed source is its own. Entries live in `~/.ratreplay/sources.json`,
ids are the first 8 hex digits of the sha256 of the resolved path.

    GET    /api/sources
    POST   /api/sources    {"path", "kind": "transformed" | "processed", "processed_path": required for transformed}
    DELETE /api/sources/{sid}                                 {"detached": sid}, the data is untouched

A source comes back as `{id, kind, path, processed_path, attached_at, status, problems, counts, manifests}`.
`status` is `ok` or `invalid` with `problems` listing what breaks the format (empty when ok), checked at each request.
`counts` holds `sessions`, `epochs`, `runs`, `frames` (a transformed source), `blocks` (once the processor ran) and
`reviews`. `manifests` holds `transformed` and `processed`, each null or `{timestamp, modified}`, the run timestamp of the
manifest and when the newest file in the folder was written. Attaching the same path again returns the entry already
recorded. A source that breaks the format is refused with 400 and every problem named.

## Sessions, transformed sources only

    GET /api/sources/{sid}/sessions
    GET /api/sources/{sid}/sessions/{session_id}
    GET /api/sources/{sid}/sessions/{session_id}/arrays

The index is a list of rows: the sessions.csv columns, `epochs`, `n_runs`, `n_clean_runs`, `in_dataset` (the session
survives the processor's funnel), `n_automatic` (the blocks the processor would build, null when there is no frames
file), then `reviewed`, `reviewed_at`, `reviewed_by`, `n_confirmed`, `confirmed_s` (seconds per epoch kind) and `notes`.
Dataset sessions come first, then unreviewed ones, then the oldest review first.

A session is two requests. The header is json: `session_id, subject_id, date, protocol, group, rate_hz, max_gap,
n_frames`, `epochs`, `block_epochs` (the epoch kinds the processor cuts into blocks), `runs`, `cuts` (`pauses` and `jumps` as frame numbers, `gaps` and `margins` as [first, last]
pairs), `heading_lost`, `heading_filled`, `heading_held` (lists of [first, last] lab frames), `led_offset` (`rad`, `r`),
`occupancy` (`bins`, the `x` and `y` extent and, by epoch name, the counts row by row from the lowest y, bins squared
values) and `blocks`, the automatic blocks. The arrays are an Arrow IPC stream (`application/vnd.apache.arrow.stream`),
one row per frame in frame order, frame number is the row index plus one: `t` s, `x` and `y` px (the mashup light),
`heading` rad (filled and corrected by the LED offset), `speed` px/s, `motion` rad (direction of motion, camera axes),
`n_lights` int8. NaN is NaN, never null.

## Reviews

    GET  /api/sources/{sid}/sessions/{session_id}/review                the review file or null
    PUT  /api/sources/{sid}/sessions/{session_id}/review                {"edits": [...], "notes": ""}
    POST /api/sources/{sid}/sessions/{session_id}/review/preview        {"edits": [...]}

An edit is `{"op", ...}`. The ops and their fields are `accept`, `confirm {frame}`, `move {frame, edge, at}`,
`split {frame}`, `drop {frame}`, `new {frame_start, frame_end}`, `cut {frame_start, frame_end}` and `flag {run}`,
listed in `GET /api/format`. The server replays them on the automatic blocks with the processor's rules, so an edit that
no longer applies is skipped. An edit anchored at a frame (`confirm`, `move`, `split`, `drop`) reaches the block
holding it, a block that is not removed before one that is, so a new block over a removed one is the one reached. PUT
writes `review/<session_id>.json` whole under the processed folder and answers
`{"review": <the file's content>, "path", "overwrote": bool}`. It is refused with 400 while a block is still auto.
POST answers `{"blocks", "cuts", "flagged_runs", "skipped"}` and writes nothing: the blocks the edits make (with the
review file's block keys), the ranges cut, the runs flagged and the edits skipped, each with a `reason` (the processor's
refusal of a new block, else that no block holds the frame it anchors to). It is the way a client shows the result of an
edit, or the skipped count of a saved review, without reimplementing the rules.

## Blocks, any source with a built processed dataset

    GET /api/sources/{sid}/blocks?{settings}
    GET /api/sources/{sid}/blocks/{block_id}?{settings}
    GET /api/sources/{sid}/blocks/{block_id}/arrays

`{settings}` are the window settings as query parameters, the project's defaults where one is left out: `window_s`,
`stride_s`, `burn_in_s`, `horizon_s`, `train_rate_hz`, `min_heading_measured`, `min_complete_trips`. The index answers
`{"blocks", "totals", "settings"}`: each block is its blocks.csv row with `heading_measured` (share of frames),
`n_windows`, `ok` and `reason` at the settings, `totals` the blocks ok and in trouble, the windows and the hours per kind
and overall. A source whose processed folder has no manifest answers 404.

A block header is json: the row's facts, `kind`, `status`, `environment`, `geometry` (`name, kind, room, boundary,
walls, centerline, reward_sites` in metres, and for a circle `circle {center, radius}`), `rate_hz`, `frame_start` (the
lab frame of the first row), `runs`, `trips` (spans with `partial`), `phases`, `heading_filled`, `heading_held`,
`one_light` (index pairs into the block), `verdict {ok, reason}`, `settings` and `windows`. Each window is `{index,
first, burn_in_stop, window_stop, stop, position_finite, heading_measured, trips_complete, trips_partial, ok}`: indices
into the block's arrays with the stops exclusive, `stop` the end of the window plus its horizon, the checks taken over
that whole range, `ok` when the position is finite throughout and the measured heading share reaches the minimum. The
arrays are an Arrow stream, one row per frame: `frame` (lab frame number), `t` s, `x` and `y` m, `heading` rad, `speed`
m/s, `n_lights`.

## Window settings

    GET /api/windows/settings
    PUT /api/windows/settings    {"settings": {...}, "source": sid}

Both answer `{"settings", "saved", "path"}`: the settings in force (the saved ones, else the defaults), the settings file
as saved (`settings, processed_manifest_timestamp, rules, totals, written_at`) or null, and where it lives. PUT writes
the file whole with the processed manifest of source `sid` and the totals over its blocks, and also answers `overwrote`.

## Format

    GET /api/format

The contract: for `transformed` and `processed` the files with their columns (name, type, `required` when the tool reads
it), for `review` the keys, block keys, statuses and edit fields, and the default `window_settings`.
