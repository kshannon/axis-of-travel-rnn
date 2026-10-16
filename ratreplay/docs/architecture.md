# RatReplay architecture

A standalone review tool for rat trajectory data: attach data folders in a known format, replay
sessions, confirm the blocks a processor will build, inspect built blocks and training windows,
and write small files that downstream tools read. Built here inside the project with pixi, meant
to become its own repository later. Localhost only, the data never leaves the machine.

This document is the design the code is reviewed against. Decisions, not options.

## Layering (volatility based, after Löwy)

    clients          the pages: data, sessions, replay, blocks, windows, api, about
    managers         one per use case: sources, sessions, review, blocks, windows
    engines          the algorithms: cuts (from process_lab_data.select), heading (offset, fills),
                     windows (from axis_of_travel_rnn.windows), kinematics (trajectory)
    resource access  stores: transformed (tables and frames), processed (blocks and manifest),
                     review (one json per session), settings (lab_blocks.yaml), registry (sources.json)
    utilities        arrow encoding, ids, time formatting

Rules: a client talks to managers over HTTP only. A manager calls engines and stores, never another
manager. Engines are pure functions over arrays. Stores do file I/O and nothing else. Science never
lives in the tool: cuts, fills, offsets and windows are imported from the project packages. Nothing
is reimplemented in TypeScript except drawing and interaction.

## Backend, `ratreplay/backend/ratreplay_api/`

FastAPI on 127.0.0.1, one process, no database. Files are the state.

    app.py                 create_app(registry_path), routes mounted, static frontend served at /
    registry.py            sources.json under ~/.ratreplay (attach, detach, list), idempotent
    stores/transformed.py  sessions, epochs, runs csv, frames parquet per session, manifest
    stores/processed.py    blocks csv, block parquet, manifest
    stores/review.py       read, write (overwrite whole), list, per session
    stores/settings.py     lab_blocks.yaml read and write
    engines/               thin wrappers naming the project functions used, nothing else
    managers/sources.py    attach validates the format contract, counts, mtimes, status
    managers/sessions.py   the session payload: arrays, epochs, runs, cut points, fills, auto blocks
    managers/review.py     apply edits (process_lab_data logic), save, reload
    managers/blocks.py     block index, block payload in metres with the environment, verdicts
    managers/windows.py    window counts, verdicts, settings save
    arrow.py               numpy dict to Arrow IPC bytes

### API (all JSON unless noted, errors as {"error": text} with 4xx)

    GET  /api/sources                      attached sources with kind, path, status, counts, mtimes
    POST /api/sources {path, kind}         attach (validate, record), returns the source
    DELETE /api/sources/{id}               detach (the data is untouched)
    GET  /api/sources/{id}/sessions        session index rows (rat, date, protocol, in_dataset, epochs,
                                           runs, automatic blocks, review facts)
    GET  /api/sources/{id}/sessions/{sid}  session payload as Arrow IPC (arrays) plus a JSON header
                                           (epochs, runs, cut points, fill spans, auto blocks, offset)
    GET  /api/sources/{id}/sessions/{sid}/review      the review file or null
    PUT  /api/sources/{id}/sessions/{sid}/review      body is the edits and notes, server applies and
                                                      writes the file whole, returns the saved review
    GET  /api/sources/{id}/blocks                     block index with verdicts at given settings
    GET  /api/sources/{id}/blocks/{bid}               block payload (Arrow) plus header (environment
                                                      geometry, runs, trips, windows at settings)
    GET  /api/windows/settings  PUT /api/windows/settings   lab_blocks.yaml
    GET  /api/format                       the data format contract as JSON (files, columns, dtypes)
    GET  /api/openapi.json                 FastAPI's schema (the API page renders both)

Source ids are short hashes of the path. A `transformed` source needs sessions.csv, epochs.csv,
runs.csv, frames/, manifest.json. A `processed` source needs manifest.json and the kind folders.
Reviews live under the processed root's `review/`, so a transformed source is paired with a
processed root in the registry entry.

## Frontend, `ratreplay/frontend/`

Vite, TypeScript, Alpine.js for page state, D3 for scales, zoom, colour and canvas drawing,
Tailwind for layout. No framework beyond that.

    src/main.ts            boot, router (hash based), theme
    src/api/               typed client, Arrow decoding, one function per endpoint
    src/state/             Alpine stores: scalars and small lists only, never frame arrays
    src/session/           the loaded session's arrays as plain typed arrays, playback clock
    src/draw/timeline.ts   lanes on canvas: session, runs, frames, blocks (and windows, trips on the
                           blocks page), D3 zoom with wheel and drag, feature layers on and off
    src/draw/map.ts        the map canvas: occupancy, trail, point, heading arrow, environment
    src/pages/*.ts         one module per page, builds its cards and wires Alpine to the engines
    src/ui/                cards, buttons, chips, toasts, the keyboard essentials

UX rules: one fixed viewport, no page scroll, cards in a grid that flexes to the window, dark by
default with a light toggle, desktop only. Every action gets feedback: a toast on save that names
the file written and whether it overwrote one. Essential keys only: space, left and right (frame,
with shift one second), `[` `]` run, enter confirm, escape clear, z undo. Everything else is a
button or a chip.

## Pages

1. Data: attached sources as cards (kind, path, status, counts, manifest time, last modified),
   attach form, detach. The entry point.
2. Sessions: a sortable index (click a header), one row per session, a row expands to its details
   (epochs with durations, runs, pauses, gaps, LED offset, review facts, automatic blocks), open.
3. Replay: the session review. Map, playback, timeline with lanes and feature chips (pauses,
   gaps, jumps, margins, heading lost, heading filled, heading held), zoom controls (whole session,
   zoom in, zoom out, fit block) besides the wheel, block cards with accept and reject, marks,
   split, remove, flag, undo, save with feedback.
4. Blocks: a sortable index of built blocks with verdicts, a block player in metres with the
   environment drawn, lanes for runs, trips and windows.
5. Windows: step through the windows of a block (previous, next, jump), each with its checks
   (position finite, heading measured share, trips inside, burn-in and horizon marked) and a
   per-window ok or trouble, totals for the block.
6. API: the format contract and the OpenAPI schema rendered as readable tables.
7. About: what the tool is, the rules it follows (never edits data, never removes behaviour), links.

## Testing

pytest for the backend: unit tests on managers and stores against synthetic folders, API tests
through FastAPI's test client for each route. Vitest for the TypeScript that holds logic: timeline
geometry (time to pixel and back under zoom), window math mirrored from Python against a shared
fixture file, state transitions of the review editor, key handling. Playwright for a few flows in
a real browser: attach a source, open a session, confirm a block, save, reload shows it, open a
block, step windows. No tests of styling.

## Working rules

Small commits, one purpose each. Plain code: named values at the top, one-line docstrings, no
semicolons or dashes in prose. The old `src/ratreplay` is not touched and stays until parity.
Builders are Sonnet, every pass is reviewed by Opus against this document.
