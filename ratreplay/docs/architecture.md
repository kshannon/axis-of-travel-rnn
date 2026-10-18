# RatReplay architecture

RatReplay turns transformed lab recordings into training ready real and synthetic trajectory
datasets, every block either human confirmed or carrying its provenance. It runs on localhost in one
process, the data never leaves the machine, and it is self contained: nothing is driven from a CLI or a
pixi task. It lives in this repository with its own backend and frontend so it can become its own
repository. Training is out of scope: the export (two data folders and a `windows.json`) is read as
files by a separate RNN project.

This document is the design the code is reviewed against. Decisions, not options. The thinking behind
them is in the working notes (`tmp/documents/ratreplay_contract.md` and
`tmp/documents/ratreplay_design_checklist.md`, uncommitted), including the Löwy checklist the design
was scored against.

## Objectives, from AGENTS.md

Nothing that encodes axis of travel reaches training (the RNN project enforces this on its inputs, the
blocks carry heading and labels for validation). Behavior generation is validated against real behavior
before it feeds training. Real recordings never enter the repository, they stay in the configured
folders. Artifacts are write once with provenance, seeds explicit, failures kept.

## Core use cases

The pipeline. Everything else is a side effect and must work but does not shape the design.

1. Review a session and save its blocks.
2. Generate a synthetic set from the real blocks and compare the two.
3. Judge a dataset's readiness at window settings and select the settings for export.

Required behaviors, as the researcher does them: see the health of the configured folders and the
specific problem when there is one. Find a session, replay it, see where the rules would cut it and why.
Accept, split, remove, make, flag and annotate blocks, undo, and see what each block yields in windows
while deciding. Save a session's blocks and get them back on the next load. Rebuild every session's
blocks after a rule change. Fit a recipe to real blocks, generate a synthetic set from it with a seed,
compare the two. Test window settings on real or synthetic blocks, step the windows of one block, select
the settings for export. Delete a synthetic set. Read what the tool is and the rules it follows.

## Glossary

Session: one recording of one rat on one day, the unit of review. Epoch: a stretch of a session under
one condition (arena, track, rotated track). Run: one traversal of a path in the lab's labelling (paths
1 to 4 outbound, 9 and 10 return). Trip: outbound run, dwell, return run, dwell, what a track block
must hold at least once to be training ready. Block: a continuous stretch of one epoch with no pause, gap or jump, at least 10 s, the
unit that is kept or removed and the unit of export. Initial blocks: the cuts the rules make before any
person edits. Review: a person's edits and notes on one session, one json file, the only thing a person
writes. Built blocks: parquet files in metres at the lab rate (60 Hz) with trip and phase labels, written from a
review. Metadata: per session, what the build used (rules, settings, review stamp, code version, built
at) and per block the window count and verdict at those settings, informative, readiness recomputes them.
Window: a fixed length slice of a block at a stride with burn-in and horizon, cut by the RNN project,
never stored here. Settings: window length, stride, burn-in, horizon, rate. Readiness: the verdicts of
the windows of a dataset at given settings. Recipe: the statistics of real blocks the generator fits.
Set: one synthetic generation with its provenance. Environment: the geometry of the track or arena and
its registration to the camera. Export: the processed and synthetic folders and `windows.json`.

## Volatility

The decomposition follows what changes, on two axes: during this project (now) and once the tool
outlives it (later). A row low on both gets no component.

| Area of change | Now | Later | Encapsulated in |
|---|---|---|---|
| How a person reviews (UI rounds, cards, keys, what a save means) | high | medium | the pages, ReviewManager |
| Cutting and labelling rules and thresholds | high | medium | TrajectoryEngine, every rule a parameter |
| Window settings and readiness criteria | high | medium | parameters on `windows`, ValidationManager |
| What is stored per session and how, the export | medium | high | ProcessedAccess, SyntheticAccess |
| Where the folders are, what the lab's files look like | low | high | TransformedAccess, the config utility |
| Environment geometry and registration | medium | high | EnvironmentAccess, TrajectoryEngine |
| How synthetic behavior is generated | high | high | GeneratorEngine |
| What the recipe measures, how real and synthetic compare | medium to high | medium | TrajectoryEngine.recipe, SynthesisManager |
| Who the client is | low | low | no component, the HTTP entry |
| Rate, units, the block schema | low | low | no component, constants and schema in the accesses |
| MATLAB to transformed conversion | low | medium | stays a project script, joins later as a fourth manager |

Weak volatilities given no component: toasts and feedback (client), clock and ids (utilities), hosting.

## Static architecture

Arrows point in the direction of the call.

```mermaid
flowchart TB
    subgraph Clients["Clients (who)"]
        UI["Web app. Pages as views: Data, Sessions, Replay, Blocks, Windows, Synthetic. About and API are client only"]
    end
    subgraph Managers["Managers (what), stateless classes, one family of use cases each"]
        RM["ReviewManager: index, load, preview edits, save blocks, rebuild all"]
        SM["SynthesisManager: generate a set from a recipe, compare, delete a set"]
        VM["ValidationManager: folder health, readiness at settings, select the settings, windows of a block, replay a built block"]
    end
    subgraph Engines["Engines (how), stateless classes, one contract each, a few operations"]
        TE["TrajectoryEngine: funnel, session, apply, blocks, windows, recipe"]
        GE["GeneratorEngine: session(recipe, environment, seed, length)"]
    end
    subgraph RA["ResourceAccess (how, for state), one per resource, schema and validation inside, atomic verbs"]
        TA["TransformedAccess"]
        PA["ProcessedAccess: blocks, metadata, reviews, windows.json"]
        SA["SyntheticAccess: sets with provenance"]
        EA["EnvironmentAccess"]
    end
    subgraph Resources["Resources (where)"]
        RT[("transformed folder, TRANSFORMED_LAB_DATA")]
        RP[("processed folder, PROCESSED_LAB_DATA")]
        RS[("synthetic folder, SYNTHETIC_DATA")]
        RE[("configs/environments yaml")]
    end
    subgraph Utilities["Utilities bar, every layer may call, no business meaning"]
        UC["config: reads configs/local.yaml for the composition root"]
        UT["tables: csv, parquet"]
        UA["arrow encoding"]
        UK["clock, paths, ids"]
    end

    UI -->|Sessions, Replay, Rebuild all on Data| RM
    UI -->|Synthetic| SM
    UI -->|Data, Blocks, Windows| VM

    RM --> TE
    RM --> TA
    RM --> PA
    RM --> EA
    SM --> TE
    SM --> GE
    SM --> PA
    SM --> SA
    SM --> EA
    VM --> TE
    VM --> TA
    VM --> PA
    VM --> SA
    VM --> EA

    TA --> RT
    PA --> RP
    SA --> RS
    EA --> RE
```

### Rules

- The architecture is closed. A component calls the layer beneath it and utilities, nothing else.
  Clients call managers only, one manager per use case. Managers call engines and accesses. Engines
  take arrays in, give arrays out, and call only utilities. An access calls its one resource.
- Nobody calls upward or sideways: engines never call engines, accesses never call accesses, managers
  never call managers. There is no bend anywhere in this design.
- Every component is a class with no state of its own, named by the book (noun plus Manager, Engine or
  Access), constructed once at the composition root in `app.py` with the components it calls. A manager
  gets its engines and accesses, an access gets its root. Nothing imports a sibling, tests hand in fakes.
  A component may have private helper modules of its own (`engines/trajectory/`, the environment
  access's builders), imported by that component alone, which the layering test pins.
- Managers are workflows, almost expendable: a change to a use case changes a manager's workflow and the
  pages, never the engines or accesses beneath. Each rule and threshold is a parameter of an engine
  operation. Each access owns its resource's schema, layout and validation errors and exposes whole,
  idempotent business verbs, never file paths or CRUD.
- UI state (selection, zoom, cursor, layers, the loaded arrays, the window settings being tried) lives in
  the client. The server stores nothing between requests, files are the state.
- Window settings are a parameter on every call that needs them. They are recorded in the per session
  metadata when blocks are built and in `windows.json` when selected for export, never held globally.
- The science lives in the two engines and nowhere else. Nothing is reimplemented in TypeScript except
  drawing and interaction.
- One named exception to the arrows: `schemas.py`, the request bodies the routers validate, reads two
  constants two layers down, the edit fields from `access.processed` and the default settings from
  `engines.trajectory`, so the API's defaults and the stored format cannot drift apart. The layering
  test pins it to exactly those two. Unknown keys in a body are refused, never dropped.

## Components

### TrajectoryEngine

One contract, six operations, every rule and threshold a parameter (`rules`, `settings`).

- `funnel(tables, rules)`: from the sessions, epochs and annotations tables and the ids with frames,
  per session whether it is in the dataset and why not (protocol, condition, excluded group,
  annotation, no frames), and the epochs the rules select. What the index shows without reading frames.
- `session(arrays, environment, rules)`: kinematics in metres, heading offset and fills (interpolated up
  to the fill limit, held when still, else missing), stops, cut points (pauses, gaps, jumps with
  margins, epoch bounds), spans (heading lost, filled, held, margins), occupancy, initial blocks, and
  the rules it used. What the Replay page draws, and what `apply` reads its rules from.
- `apply(blocks, edits, session)`: the edit legality rules (no overlap with a kept block, no kept block
  under the minimum length, no block outside its epoch, no edit on a removed block, a moved edge snaps
  to a run edge within `snap_s`), the resulting blocks and the refusals with reasons.
- `blocks(arrays, review, environment, rules)`: the labelled blocks (trip, phase, frames in metres at
  the lab rate) for a session, from the review's blocks or the initial blocks when there is none.
  The same call for real and generated arrays.
- `windows(block, settings, rules)`: the window rows (start, end, burn-in, horizon, complete and
  partial trips inside, measured heading share, position finite) and the verdict of each, plus the
  block's verdict listing every rule it breaks (no window fits, measured heading share under the minimum
  over the block, and on a track block only, fewer complete trips over the whole block than
  `min_complete_trips`). A window needs no trip of its own. `rules` gives the return paths that end a
  trip, the rules the block was built with. `settings["rate_hz"]` is the RNN project's resampling rate,
  recorded in `windows.json`, and plays no part here, the arithmetic runs at the block's own rate. The
  verdict rules live here only.
- `recipe(blocks)`: the statistics the generator fits and the numbers real and synthetic are compared
  on (speed and turn rate distributions, dwell times, run durations, occupancy).

### GeneratorEngine

`session(recipe, environment, seed, length)`: arrays in the transformed schema, from an explicit RNG,
so SynthesisManager blocks them with the same `TrajectoryEngine.blocks` call as real data.

### ReviewManager

`index()`, `load(sid, settings)`, `preview(sid, edits, settings)`, `save_blocks(sid, edits, notes,
settings)`, `rebuild_all(settings)`. Save blocks applies the edits first and one illegal edit refuses
the whole save with its reason, nothing written. Then it writes the review, then builds from the review
on disk (arrays, `blocks`, `windows` per block, `ProcessedAccess.write_blocks`) in one private step that
`rebuild_all` runs for every session with a review. The one partial outcome is an I/O failure of the
build after the review is written, returned as a result, not an error.

### SynthesisManager

`index()`, `generate(source sessions, generator parameters, seed, length, settings)`,
`delete_set(set id)`. Generate reads the source blocks, fits the recipe, generates, blocks and windows
the result with the same engine calls as real data, computes the recipe of the synthetic blocks for the
comparison, and writes the set with its provenance (source sessions, recipe, generator parameters,
seed, rules, settings, code version).

### ValidationManager

`health()`, `format()`, `readiness(which, settings)`, `block(block id)`, `arrays(block id)`,
`windows(block id, settings)`, `select_settings(settings)`, `selected()`. Health and format come from
the accesses alone, no engine. Readiness reads built blocks (real, or one synthetic set) and calls
`windows` on each under the rules the block's session was built with (from its metadata), it never re
cuts a session. Select settings writes `windows.json` whole, the one thing this manager writes, and is
refused while nothing is built. Selected reads it back.

### Accesses

- `TransformedAccess(root)`: `health()`, `schema()`, `sessions()`, `session(sid)` (arrays, epochs,
  runs, the manifest stamp). Read only.
- `ProcessedAccess(root)`: `health()`, `schema()`, `review(sid)`, `reviews()`, `write_review(sid,
  review)`, `blocks()`, `block(block id)`, `metadata(sid)`, `write_blocks(sid, blocks, metadata)`
  (a session's blocks, index rows and metadata replaced whole, through temporary names and a rename),
  `window_settings()`, `write_window_settings(settings)`.
- `SyntheticAccess(root)`: `health()`, `sets()`, `blocks(set id)`, `block(set id, block id)`,
  `write_set(set id, blocks, provenance)`, `delete_set(set id)`.
- `EnvironmentAccess(root)`: `health()`, `environments()`, `environment(name)` from
  `configs/environments/*.yaml`. The yaml is the compact definition (type, room, params, or a base and a
  transform) and expanding it into walls, centerline, boundary and reward sites is part of reading the
  resource, done by the access's private `environment_builders.py`. Functions over a geometry (inside,
  registration, distance to a wall) are engine maths.

Each access reports its root as a fact for the Data page, never its layout.

### Utilities

`config` (reads `configs/local.yaml`, returns a key's value or a named error, knows nothing about the
keys), `tables` (csv and parquet in and out), `arrow` (numpy dict to an Arrow IPC stream), `clock`,
`paths`, `ids`. Nothing else until a second system needs it.

## The core use cases as call chains

### 1. Review a session and save its blocks

```mermaid
sequenceDiagram
    participant P as Replay page
    participant RM as ReviewManager
    participant TA as TransformedAccess
    participant EA as EnvironmentAccess
    participant PA as ProcessedAccess
    participant TE as TrajectoryEngine
    P->>RM: load(sid, settings)
    RM->>TA: session(sid): arrays, epochs, runs
    RM->>EA: environment(name)
    RM->>PA: review(sid): review or none
    RM->>TE: session(arrays, environment, rules): kinematics, fills, cut points, spans, occupancy, initial blocks
    RM->>TE: apply(initial blocks, review.edits, session) when a review exists
    RM->>TE: windows(block, settings, rules) for each kept block
    RM-->>P: header (epochs, runs, cuts, spans, blocks with window counts, review facts) + Arrow arrays
    loop while editing
        P->>RM: preview(sid, edits, settings)
        RM->>TE: apply, then windows per kept block
        RM-->>P: blocks, refusals with reasons
    end
    P->>RM: save_blocks(sid, edits, notes, settings)
    RM->>TE: apply(...), one illegal edit refuses the whole save
    RM->>PA: write_review(sid, review)
    RM->>TE: blocks(arrays, review, environment, rules): labelled blocks in metres
    RM->>TE: windows(block, settings, rules) for each block
    RM->>PA: write_blocks(sid, blocks, metadata), whole and idempotent
    RM-->>P: result: review saved, n blocks built (or build failed with the reason)
```

Rebuild all is the lower half alone, from the Data page with a confirmation: `rebuild_all(settings)`
lists the reviews and runs the same private build step for every session.

### 2. Generate a synthetic set and compare it with the real blocks

```mermaid
sequenceDiagram
    participant P as Synthetic page
    participant SM as SynthesisManager
    participant PA as ProcessedAccess
    participant EA as EnvironmentAccess
    participant TE as TrajectoryEngine
    participant GE as GeneratorEngine
    participant SA as SyntheticAccess
    P->>SM: generate(source sessions, generator params, seed, length, settings)
    SM->>PA: blocks(source sessions)
    SM->>TE: recipe(real blocks)
    SM->>EA: environment(name)
    SM->>GE: session(recipe, environment, seed, length): arrays in the transformed schema
    SM->>TE: blocks(arrays, no review, environment, rules): same call as real data
    SM->>TE: windows(block, settings, rules) for each block
    SM->>TE: recipe(synthetic blocks): the same statistics, for the comparison
    SM->>SA: write_set(set id, blocks, provenance with both recipes)
    SM-->>P: result: set id, n blocks, the comparison table
    P->>SM: delete_set(set id)
    SM->>SA: delete_set(set id)
```

### 3. Judge readiness at window settings and select them

```mermaid
sequenceDiagram
    participant P as Blocks page, Windows page
    participant VM as ValidationManager
    participant PA as ProcessedAccess
    participant SA as SyntheticAccess
    participant TE as TrajectoryEngine
    P->>VM: readiness(which: real or a synthetic set, settings)
    alt real
        VM->>PA: blocks(): every built block with its metadata
    else synthetic
        VM->>SA: blocks(set id)
    end
    VM->>TE: windows(block, settings, rules) for each block
    VM-->>P: per block verdicts, totals, the settings the blocks were built with
    P->>VM: windows(block id, settings)
    VM->>PA: block(block id)
    VM->>TE: windows(block, settings, rules)
    VM-->>P: window rows with their checks, for stepping
    P->>VM: select_settings(settings)
    VM->>PA: write_window_settings(settings): windows.json, whole
    VM-->>P: result: the file written, new or overwritten
```

The three chains have one shape: read an access, call the engine, write or return. That symmetry is a
review check, an asymmetric chain is investigated before it is built.

### A future use case, to show the design extends without rework

The converter joins RatReplay: a `ConversionManager` over a new `LabDataAccess` (the MATLAB files),
writing through `TransformedAccess`, which gains write verbs. A fourth manager and a fifth access,
inside the counts, and the three managers above do not change.

## The operational flow

```mermaid
flowchart LR
    subgraph Lab["Outside the repository, Kyle runs it"]
        M[("MATLAB tracking and analysis files")]
        C["converter, src/transform_lab_data, pixi run transform-lab-data"]
        M --> C
    end
    C --> T[("transformed folder: sessions, epochs, runs, frames at 60 Hz in pixels")]
    subgraph RR["RatReplay, in the browser"]
        R1["Data: health of the folders, rebuild all"]
        R2["Sessions and Replay: review each session, save blocks"]
        R3["Blocks and Windows: readiness at settings, select them"]
        R4["Synthetic: fit a recipe, generate sets, compare"]
        R1 --> R2 --> R3 --> R4
    end
    T --> R1
    R2 --> Pf[("processed folder: review json, blocks parquet in metres at the lab rate, metadata per session, windows.json")]
    Pf --> R3
    Pf --> R4
    R4 --> Sf[("synthetic folder: sets of blocks with provenance")]
    Sf --> R3
    R3 --> Pf
    subgraph Out["Separate RNN project, reads files only"]
        N["training: position in, future position out, windows cut as windows.json says"]
    end
    Pf --> N
    Sf --> N
```

## Resources on disk

The three folders come from `configs/local.yaml`: `TRANSFORMED_LAB_DATA`, `PROCESSED_LAB_DATA`,
`SYNTHETIC_DATA`, read once at start by the composition root (`create_app(config_path)` takes another
file in tests). Edit the file and press Reload on the Data page to change a folder.

    transformed/   sessions.csv, epochs.csv, runs.csv, frames/{sid}.parquet, manifest.json   (read only)
    processed/     review/{sid}.json            the person's edits and notes, written whole
                   blocks/{block_id}.parquet    one built block, metres, the lab rate, trip and phase labels
                   blocks.csv                   one row per built block, a session's rows replaced together
                   metadata/{sid}.json          rules, settings, review stamp, code version, built at, and per
                                                block the window count and verdict at those settings (informative)
                   windows.json                 the selected window settings, readiness totals, when, by whom
    synthetic/     sets/{set_id}/blocks/{block_id}.parquet, blocks.csv, provenance.json
    configs/environments/{name}.yaml            the compact definition of each environment

A session's processed files are staged under temporary names and renamed into place in one short pass,
so a failure while building leaves the previous build whole. A crash inside the rename pass itself can
leave the index naming files that are gone or orphan files with no row, and health reports both
(missing block files, orphan parquet or temporary files), so the state is loud and the next save of that
session repairs it. A session with blocks on disk loads them back and overwrites them on the next save.
Block ids are the session id, the epoch and a number within the epoch, as the processor formed them.

## Backend, `ratreplay/backend/ratreplay_api/`

FastAPI on 127.0.0.1, one process, no database.

    app.py                    create_app(config_path): the composition root, routes mounted, static frontend at /
    routers/review.py         the HTTP face of ReviewManager, no logic
    routers/synthesis.py      SynthesisManager
    routers/validation.py     ValidationManager
    managers/review.py        ReviewManager
    managers/synthesis.py     SynthesisManager
    managers/validation.py    ValidationManager
    engines/trajectory/       TrajectoryEngine in __init__.py, private modules behind it (cuts, heading,
                              labels, edits, windows, recipe, geometry), pure functions over arrays
    engines/generator.py      GeneratorEngine
    access/transformed.py     TransformedAccess, with the transformed schema
    access/processed.py       ProcessedAccess, with the review, block, metadata and windows.json schemas
    access/synthetic.py       SyntheticAccess, with the set and provenance schemas
    access/environment.py     EnvironmentAccess, with environment_builders.py as its private helper
    utilities/                config, tables, arrow, clock, paths, ids, errors (the error shape)

The old `src/process_lab_data` and `src/axis_of_travel_rnn.windows` are not imported: their science is
moved into `engines/trajectory/` and they are removed once a real dataset has been built with this tool.

### API

JSON unless noted, errors as `{"error": text}` with 4xx, results as objects. Window settings travel as
query parameters on GET and in the body otherwise.

    GET  /api/health                         the three folders: root, exists, problems, counts, times, the config file
                                             (?reload=true reads the config again first)
    GET  /api/format                         the schemas each access declares (files, columns, dtypes)
    GET  /api/sessions                       index rows (rat, date, protocol, epochs, runs, initial blocks, review facts)
    GET  /api/sessions/{sid}                 header: epochs, runs, cuts, spans, blocks with window counts, offset, review,
                                             the environments geometry, warnings, refusals, in_dataset and reason
    GET  /api/sessions/{sid}/arrays          the arrays as an Arrow IPC stream
    POST /api/sessions/{sid}/preview         body edits and settings, returns blocks and refusals, writes nothing
    PUT  /api/sessions/{sid}/blocks          body edits, notes, settings, saves the review and builds the blocks
    POST /api/rebuild                        body settings, rebuilds every reviewed session, returns counts
    GET  /api/blocks?which=real|set:{id}     readiness: block rows with verdicts at settings, totals, built settings
    GET  /api/blocks/{bid}                   header: row with rate_hz, environment geometry, runs, trips, phases, heading spans (and /arrays as Arrow)
    GET  /api/blocks/{bid}/windows           window rows with their checks at settings
    GET  /api/windows   PUT /api/windows     the selection {"selected": windows.json or null}, and select (returns replaced and file)
    GET  /api/sets   POST /api/sets          synthetic sets, and generate one (body: sources, params, seed, length, settings)
    DELETE /api/sets/{id}
    GET  /api/openapi.json                   FastAPI's schema, the API page renders it with /api/format

## Frontend, `ratreplay/frontend/`

Vite, TypeScript, Alpine.js for page state, D3 for scales, zoom, colour and canvas drawing, Tailwind for
layout. No framework beyond that.

    src/main.ts            boot, hash router, theme
    src/api/               typed client, Arrow decoding, one function per endpoint
    src/state/             Alpine stores: scalars and small lists only (health, the settings being tried), never arrays
    src/session/           the loaded session's arrays as typed arrays, playback clock, the editor's edit list
    src/draw/              timeline lanes and the map on canvas, zoom, feature layers, environment, occupancy
    src/pages/             one module per page, builds its cards and wires Alpine to the api client
    src/ui/                cards, buttons, chips, toasts, tables, the keyboard essentials

The client holds no rule. Drawing geometry (metres to pixels, lane layout) is presentation and stays.
Window math is not mirrored, the block cards show what the manager returned.

UX rules: one fixed viewport, no page scroll, cards in a grid that flexes to the window, dark by default
with a light toggle, desktop only. Every action gets feedback, a toast on a write names the file and
whether it overwrote one. Essential keys only: space, left and right (frame, with shift one second),
`[` `]` run, enter confirm, escape clear, z undo. Everything else is a button or a chip.

## Pages

1. Data: the path the data takes, the three folders as cards (root, status, problems, counts, times),
   the config file, Reload, and Rebuild all on the processed card with a confirmation. The entry point.
   The other pages gate on the health of the folder they need.
2. Sessions: a sortable index, a row expands to its details, Open in replay.
3. Replay: the review. Map, playback, timeline with lanes and feature chips, zoom controls, block cards
   with window counts at the settings being tried, accept, reject, marks, split, remove, flag, notes,
   undo, Save blocks with its result toast.
4. Blocks: readiness. Real or a synthetic set, the settings being tried, a sortable index with verdicts
   and the settings each session was built with, totals, Select these settings, a block player in metres
   with the environment and lanes for runs, trips and windows.
5. Windows: step through the windows of one block, each with its checks and verdict.
6. Synthetic: the sets with their provenance and comparison, generate (sources, parameters, seed, length),
   delete.
7. API: `/api/format` and the OpenAPI schema as readable tables.
8. About: what the tool is, the rules it follows (never edits data, never removes behavior), the glossary.

## Testing

Heavy unit tests on the engines only, a few integration tests per manager, a few system tests. Tests do
not sit beside the code they test.

    backend/tests/unit/          TrajectoryEngine and GeneratorEngine: rules, thresholds, edge cases, parity with the
                                 old processor and tool until they are removed
    backend/tests/integration/   one file per manager, real accesses over synthetic folders, a handful of use case
                                 walks each, no HTTP
    backend/tests/system/        a few flows through the HTTP client: save blocks, rebuild all, health, readiness
    frontend/tests/              Vitest on the pure TypeScript: timeline geometry, the editor's state transitions, keys
    frontend/e2e/                Playwright, two or three flows in a real browser

`backend/tests/unit/test_layering.py` asserts the import graph of the chart: routers import managers,
managers import engines and access, engines import utilities only, access imports utilities only.

## Migration from the current code

| Today | Becomes |
|---|---|
| `stores/data_sources.py` | gone, `app.py` reads the config utility and wires the accesses |
| `stores/settings.py`, `configs/datasets/lab_blocks.yaml` | gone, `windows.json` through `ProcessedAccess` |
| `stores/transformed.py` | `access/transformed.py`, TransformedAccess |
| `stores/processed.py`, `stores/review.py` | `access/processed.py`, ProcessedAccess |
| `stores/folder.py`, `schemas.py`, `contract.py` | inside the accesses and `utilities/tables.py` |
| `engines/cuts.py, heading.py, edits.py, windows.py, occupancy.py, spans.py, environment.py` and the science they import from `src/` | `engines/trajectory/`, TrajectoryEngine, the science moved in |
| new | `engines/generator.py`, `access/synthetic.py`, `access/environment.py`, `managers/synthesis.py` |
| `managers/sessions.py`, `managers/review.py` | `managers/review.py`, ReviewManager |
| `managers/sources.py`, `managers/blocks.py`, `managers/windows.py` | `managers/validation.py`, ValidationManager |
| `routers/*` | three routers, one per manager |
| `arrow.py`, `clock.py`, `errors.py` | `utilities/` |
| `frontend/src/session/windows.ts` and its test | gone, the client shows what the manager returns |
| `frontend/src/state/sources.ts` | `state/health.ts` |
| `frontend/src/**/*.test.ts` | `frontend/tests/`, cut to the pure modules |
| `frontend/e2e/*.spec.ts` | two or three flows |

Build order, by layers: utilities, then accesses, then engines, then managers and routers, then pages,
with the system tests last. The old `src/ratreplay` and `src/process_lab_data` are removed in their own
commit once a real dataset has been built with this tool.

## Working rules

Small commits, one purpose each. Plain code: named values at the top, one line docstrings, no semicolons
or dashes in prose. Builders are Sonnet, every pass is reviewed by Opus against this document and the
layering test. Never the labnotebook files. Kyle runs everything that touches real data.
