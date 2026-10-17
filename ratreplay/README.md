# RatReplay

A standalone review tool for rat trajectory data: read data folders in a known format, replay
sessions, confirm the blocks a processor will build, inspect built blocks and training windows.
Localhost only. It lives here with its own backend and frontend so it can become its own
repository. The old Dash tool in `src/ratreplay/` is no longer imported here and stays until the authors delete it.

The design, layering, API, pages and testing plan are in [docs/architecture.md](docs/architecture.md).
The API as built is in [backend/README.md](backend/README.md).

## Run

Node comes from pixi through the `ratreplay` environment, `pixi run` finds it for the tasks below.

    pixi run ratreplay-install    # once: the frontend's npm packages
    pixi run ratreplay-build      # the frontend into ratreplay/frontend/dist
    pixi run ratreplay-api        # http://127.0.0.1:8060, the API and the built frontend (--port N)

## Using

**Data folders.** The two folders come from `configs/local.yaml`, the `TRANSFORMED_LAB_DATA` and `PROCESSED_LAB_DATA`
keys the processor reads, so the tool and the processor never disagree about where the data is. The transformed folder is
the converter's output. The processed folder is where the reviews are written and the processor builds its blocks, it
need not exist yet. The Data page shows the path the data takes, each folder with its resolved path, whether it follows
the data format (the API page lists it), every problem if not, its counts and times, and the config file. To change a
folder edit that file and press Reload. A page that needs a folder shows its problem and a link to the Data page until
the folder is ok.

**Review a session.** The Sessions page lists one row per session, the sessions of the dataset first. A click on a
header sorts, a click on a row opens its details, and Open in replay loads it. The Replay page plays the session
and draws it on a timeline with the cuts the processor makes. Select a block by its card or its bar, accept it,
reject it (a second click takes it back), move its start or end to the cursor, or split it at the cursor. Mark a
range with Mark in and Mark out and make a block of it, flag a run, undo, reset to the automatic blocks and write
notes. The server applies every edit with the processor's rules and says why it skipped one. Save session writes
the review whole and opens the next session to review. It is refused while a block is still automatic.

**Build blocks with the processor.** `pixi run process-lab-data` reads the reviews under the processed folder and
builds the kept blocks of the sessions reviewed, and the automatic blocks of the others (`--confirmed-only` leaves
those out).

**Inspect blocks and windows.** The Blocks page lists the built blocks with their verdicts at the window settings
and the totals. Open a block to play it in metres over its environment with the lanes of its runs, trips and
windows. Step through its windows opens the Windows page, which shows one window at a time with its checks and a
verdict for it.

**Save settings.** The inputs on the Blocks page are the window settings. Test on all blocks shows the verdicts at
them without writing anything, and Save settings writes the file the training pipeline reads, with the totals at
those settings. The block cards of the Replay page count windows at the saved settings.

**Where every file is written.** Nothing else is written and the data folders are only read.

| What | Where |
| --- | --- |
| a session's review | `review/<session_id>.json` under the processed folder, overwritten whole on each save, the toast names it |
| the window settings | `configs/datasets/lab_blocks.yaml` in the repository, overwritten whole on each save |
| the theme and the session open in the replay | the browser's local storage |

**Keys.** Everything else is a button or a chip.

| Key | Action |
| --- | --- |
| space | play and pause |
| left, right | one frame back or forward, on the Windows page the previous or next window |
| shift with left, right | one second back or forward |
| `[` and `]` | previous and next run |
| enter | confirm the selected block |
| escape | clear the selection and the marks |
| z | undo the last edit |

## Development

    pixi run ratreplay-ui         # Vite with hot reload, /api proxied to port 8060
    pixi run ratreplay-test       # pytest on the backend, then vitest on the frontend

`ratreplay-build` runs the strict TypeScript check before it builds. The Playwright flows run against the built
frontend, so build first:

    pixi run -e ratreplay npm --prefix ratreplay/frontend exec -- playwright install chromium   # once
    pixi run -e ratreplay npm --prefix ratreplay/frontend run e2e

The flows use `frontend/e2e/serve_synthetic.py`, which rebuilds the backend tests' synthetic folders under
`$TMPDIR/ratreplay-e2e` on each start, writes a `local.yaml` there naming them and serves the API on that config, with
its window settings and reviews in the same folder. Nothing outside it is touched, no real data and not the
repository's `configs/local.yaml`. The server shares one port, so the flows run one at a time and each puts back what it
changed.

The backend imports the project packages, so after pulling a change to the `packages` list in
`pyproject.toml` run `pixi reinstall axis-of-travel-rnn` once.

## Layout

    backend/ratreplay_api/   FastAPI: routers, managers, engines, stores
    backend/tests/           pytest on synthetic folders, the API through the test client
    frontend/                Vite, TypeScript, Alpine, D3 and Tailwind: pages, drawing, the typed API client
    docs/architecture.md     the design the code is reviewed against

## Status

Every page of the design is built, and nothing under `backend/ratreplay_api` imports the old Dash tool in `src/ratreplay`
any more: the edit rules live in `engines/edits.py` and the checks of each window in `axis_of_travel_rnn.windows`. The old
tool is only imported by `backend/tests/test_parity.py`, on purpose, since it is the oracle. It runs the same edits through
this API and through the old tool and finds the same review files, session facts and arrays, apart from the two differences
in [backend/README.md](backend/README.md#differences-from-the-old-tool). Both tools read and write the same review files and
settings file, so either can be used meanwhile, and the old tool and `test_parity.py` are deleted together.

What `src/ratreplay` still does and this does not:

- Keys for every action: `a`, `n`, `i`, `o`, `,`, `.`, `s`, `d`, `f` and `{`, `}` to jump between blocks. They were
  dropped on purpose, the actions are buttons here.
- A click on a block's glyph accepts it and a right click on a run flags it.
- It opens on the first session to review, where here a session is chosen on the Sessions page.
