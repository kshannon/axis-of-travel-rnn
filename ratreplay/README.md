# RatReplay

RatReplay turns the lab's transformed recordings into training ready trajectory blocks. A person replays each
session in the browser, accepts, splits, removes or makes blocks, and saves. Saving writes the review and builds the
session's blocks in metres at the lab rate (60 Hz) with trip and phase labels. The tool also judges which blocks are
ready to train on at window settings you try, and selects the settings for export.

It runs on localhost in one process and the data never leaves the machine. Nothing is driven from a command line or a
pixi task beyond starting it. It lives in this repository with its own backend and frontend so it can become its own
repository. Training is out of scope: a separate RNN project reads the export as files. Nothing that encodes axis of
travel may reach training, so the blocks carry heading and labels for validation and the RNN project keeps them out of
its inputs. Real recordings stay in the configured folders.

The real slice is built. The synthetic slice (a generator, a Synthetic page and the `SYNTHETIC_DATA` folder) is not, and
the Blocks page judges the real dataset only.

## Run

Node comes from pixi through the `ratreplay` environment, `pixi run` finds it for the tasks below.

    pixi run ratreplay-install    # once: the frontend's npm packages
    pixi run ratreplay-build      # type checks the frontend and builds it into ratreplay/frontend/dist
    pixi run ratreplay-api        # http://127.0.0.1:8060, the API and the built frontend (--port N)

The folders come from `configs/local.yaml`, git-ignored, made by copying `configs/local.example.yaml`. Three keys:

- `TRANSFORMED_LAB_DATA`: the converter's output, read only.
- `PROCESSED_LAB_DATA`: where reviews, built blocks and `windows.json` are written. It need not exist, the first save creates it.
- `SYNTHETIC_DATA`: arrives with the synthetic slice, nothing reads it yet.

The environments are the repository's `configs/environments/*.yaml`, not a key. The API reads the config file when it
starts. To change a folder, edit the file and press Reload on the Data page.

## Using it

The flow is the one the About page explains: Data, Sessions and Replay, Blocks and Windows, then the export. The converter
runs before all of it, outside the tool (`pixi run transform-lab-data`, see the root README). There is no batch
processor. A session's blocks are built when a person saves it, or by Rebuild all, so a session with no review has none.

**Data.** Cards show the transformed folder, the processed folder and the environments, each with its path, status,
every problem found, counts and times, and one shows the config file with Reload. Rebuild all, on the processed card,
builds the blocks of every reviewed session again from its review after a confirmation, for when a rule changed. It
builds at the selected settings when `windows.json` exists, else at the settings in use, and never changes a review. A
page that needs a folder shows its problem and a link to this page until the folder is ok.

**Sessions and Replay.** Sessions lists one row per session with an arena or track epoch, the sessions of the dataset
first. A click on a header sorts, a click on a row shows its epochs, blocks and review, and Open in replay loads it.
A session the rules leave out is greyed, with the reason in its details. With frames it can be viewed and previewed but
not saved: Save blocks is disabled and the API refuses with the reason.

Replay plays the session over a timeline with the cuts the rules make. Each block is a card with its window count and
verdict at the settings being tried. Accept or Reject a block, move its start or end to the cursor, split it at the
cursor, mark a range and make a block of it, flag a run, write notes, undo, or reset to the automatic blocks. The server
applies every edit and says why it refused one, and a preview writes nothing. Save blocks is refused while a block is
still automatic. It writes `review/<session_id>.json` and builds the session's blocks. The toast names the review file
and whether it replaced one, and warns if the build failed or a block failed a check. Then the next session to review
opens. A saved session loads with its review.

Keys: space plays, left and right step a frame (with shift a second, on the Windows page a window), `[` and `]` jump a
run, enter confirms the selected block, escape clears the selection, z undoes. Everything else is a button or a chip.

**Blocks and Windows.** Blocks judges the built blocks at the window settings being tried: window, stride, burn-in,
horizon, the rate the RNN project resamples to (recorded, not used in the counts), the least measured heading share and
the least complete trips on a track block. Each block gets a window count and a verdict listing every rule it breaks.
The totals follow, and a row opens to compare the settings tried with the ones its session was built with. The settings
start from the selection in `windows.json`, else the defaults, and the Replay cards count at the same settings.
Select these settings writes `windows.json` whole, and the toast names it and whether it replaced one. It is refused
while nothing is built. Open a block to play it in metres over its environment, and Step through its windows opens the
Windows page, one window at a time with its checks. The Data page shows the data format, the About page the process,
the rules the tool follows and the internal routes. Nothing else is written, the transformed folder and the environments are only read.

## The export

    processed/
      review/{session_id}.json     the person's edits and notes, written whole on each save
      blocks/{block_id}.parquet    one built block, in metres at 60 Hz, one row per frame
      blocks.csv                   one row per built block
      metadata/{session_id}.json   what a build used, and per block its window count and verdict then
      windows.json                 the settings selected for export

A block id is the session id, the epoch and a number within the epoch. A block's parquet holds `frame` (the lab frame
number), `t`, `x`, `y`, `heading`, `speed`, `turn_rate`, `n_lights`, the fill flags, `phase`, `trip`, `run`, `path_id`
and `clean`. `blocks.csv` holds the block's session, epoch, frames, duration, rate, run and trip counts, seconds of
heading lost, filled and held, status, reviewer, and the registration and kinematics version it was built under.
`windows.json` holds `settings`, `totals` (blocks, ok, trouble, windows, windows_ok at those settings), `selected_at`
and `selected_by`.

The RNN project reads these files and cuts the windows itself as `windows.json` says, so windows are never stored here.
Heading, phase and trip are for validation and analysis, not training inputs. A build writes a session's files under
temporary names and renames them in one short pass, so a failed build leaves the previous one whole. A block that fails a
check is not written and is listed under `failed` in the session's metadata. The Data page reports leftover temporary
files, missing block files and orphan block files as problems. The synthetic folder joins the export with its slice.

## Testing

    pixi run ratreplay-test       # pytest on the backend, then vitest on the frontend
    pixi run ratreplay-ui         # Vite with hot reload, /api proxied to port 8060 (run the API too)

    backend/tests/unit/           the engines, accesses and utilities, and the import layering of the backend
    backend/tests/integration/    one file per manager, real accesses over synthetic folders, no HTTP
    backend/tests/system/         the flows through the HTTP client: save, rebuild, readiness, select, health, refusals
    frontend/tests/               Vitest on the pure TypeScript: geometry, the editor, keys, formats
    frontend/e2e/                 Playwright flows in a real browser, against the built frontend

Every test uses synthetic folders, never real data and never `configs/local.yaml`. The Playwright flows need the
build first and a one time browser install:

    pixi run -e ratreplay npm --prefix ratreplay/frontend exec -- playwright install chromium   # once
    pixi run -e ratreplay npm --prefix ratreplay/frontend run e2e

Some backend tests (the fixtures and the parity tests) still import the old processor and Dash tool as the oracle. After
a change to the `packages` list in `pyproject.toml`, run `pixi reinstall axis-of-travel-rnn` once.

## More

The design is in [docs/architecture.md](docs/architecture.md), the order of the rebuild and the notes from building it
in [docs/plan.md](docs/plan.md), the tasks in [docs/tasks.md](docs/tasks.md), the API as built in
[backend/README.md](backend/README.md). The old Dash tool (`src/ratreplay`) and the processor (`src/process_lab_data`)
are retired by RatReplay and removed in task R2, once the first real dataset has been built with the tool.
