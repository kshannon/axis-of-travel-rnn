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

Status, 2026-10-20. The real slice is built and in daily use for making the processed data: the reviews, the blocks and
`windows.json`. The synthetic slice is built as a first pass and parked for a later EDA of the synthetic data: a recipe of
statistics measured on the real blocks, a generator (version 3) that writes a synthetic session into the `SYNTHETIC_DATA`
folder, a Synthetic page to generate and compare, and a Real or synthetic page to tell them apart by eye. It has had a
first check by eye and by recipe, not yet the validation against real behavior that the project requires before synthetic
data feeds training. The old processor and the old Dash tool are gone, the converter (`pixi run transform-lab-data`) is
the one script left.

## Run

Node comes from pixi through the `ratreplay` environment, `pixi run` finds it for the tasks below.

    pixi run ratreplay-install    # once per clone: the frontend's npm packages
    pixi run ratreplay-build      # once after a pull: type checks the frontend and builds it into ratreplay/frontend/dist
    pixi run -e ratreplay ratreplay-api   # http://127.0.0.1:8060, the API and the built frontend (--port N)

`pixi run ratreplay` is the same as the last line. After a pull that changed the backend, stop the API and start it again,
the running process does not pick up new code. The page tells you to restart it when the API is older than the page.

The API listens on 127.0.0.1 only. To use it from another machine, forward the port over ssh and open the same address on
the laptop:

    ssh -N -L 8060:127.0.0.1:8060 <host>      # on the laptop, leave it running
    # then http://127.0.0.1:8060 in the laptop's browser

The first number is the laptop's port and the second the API's, so change the second if you started it with `--port N`.

The folders come from `configs/local.yaml`, git-ignored, made by copying `configs/local.example.yaml`. Four keys belong to the
data path and RatReplay reads three of them:

- `LAB_DATA`: the lab's MATLAB files. Only the converter reads it, RatReplay never does.
- `TRANSFORMED_LAB_DATA`: the converter's output, read only.
- `PROCESSED_LAB_DATA`: where reviews, built blocks and `windows.json` are written. It need not exist, the first save creates it.
- `SYNTHETIC_DATA`: where synthetic sets are written, one folder per set. It need not exist, the first Generate creates it.

The environments are the repository's `configs/environments/*.yaml`, not a key. The API reads the config file when it
starts. To change a folder, edit the file and press Reload on the Incoming page.

## Using it

The flow is the one the About page explains, in the order of the top bar: Incoming, Settings, Replay, Blocks, Windows,
Synthetic, Real or synthetic and Outgoing, with Environments and About beside them. Eight pages are the real slice and
two (Synthetic and Real or synthetic) the synthetic one. The converter runs before all of it, outside the tool
(`pixi run transform-lab-data`, see the root README). There is no batch processor. A session's blocks are built when a
person saves it, or by Rebuild all, so a session with no review has none.

**Incoming.** A strip gives where the lab data, the environment geometry and the synthetic sets are read from and the
config file that names them, each with a status and any problem found under it, and Reload, which reads the config file
again and checks the folders. Under it the sessions: a row of tiles (in the dataset, reviewed, excluded, blocks confirmed,
confirmed hours per kind, built) and one row per session with an arena or track epoch, the sessions of the dataset first.
A click on a header sorts, a click on a row shows its epochs, blocks and review, and Open in replay loads it. Exclude and
Include record your decision to leave a session out or take it back, with a note. A session the rules leave out is greyed,
with the reason in its details. With frames it can be viewed and previewed but not saved: Save blocks is disabled and the
API refuses with the reason. The format of the transformed files is folded at the bottom. A page that needs a folder shows
its problem and a link to Incoming, or to Outgoing for the processed folder, until the folder is ok.

**Settings.** The seven window settings: window, stride, burn-in, horizon, the rate the RNN project resamples to
(recorded, not used in the counts), the least measured heading share and the least complete trips on a track block. Each
has a one line hint of what it protects and its default beside it, and a sentence under them spells out what the verdicts
are tested at. They start from the selection in `windows.json`, else the defaults, and Blocks, Windows and the Replay
cards count at the same settings. Select these settings writes `windows.json` whole, and the toast names it and whether it
replaced one. It is refused while nothing is built. Reset to the defaults puts them back. Under them the engine's rules
are listed read only, each with its value and meaning. Changing one is a code change, and a Rebuild all makes it reach
what is built.

**Replay.** Replay plays the session over a timeline with the cuts the rules make. Each block is a card with its window
count and verdict at the settings in use. Accept or Reject a block, move its start or end to the cursor, split it at the
cursor, mark a range and make a block of it, cut a marked range out of every block it touches, replace the track blocks with one block per complete trip, flag a run,
write notes, undo, or reset to the automatic blocks. The keys A and R accept and reject the selected block. Start offset, m, under Flag run is how far up the stem the start site sits for
this session (the environment's yaml gives the default and Use measured fills in the engine's reading of the data), and
Save writes it into the review. The server applies every edit and says why it refused one, and a preview writes nothing.
Save blocks is refused until every kept block is accepted, an automatic block as drawn and an edited block after a change.
It writes `review/<session_id>.json` and builds the session's blocks. The toast names the review file and whether it
replaced one, and warns if the build failed or a block failed a check. Then the next session to review opens. A saved
session loads with its review.

Keys: space plays, left and right step a frame (with shift a second, on the Windows page a window), `[` and `]` jump a
run, enter confirms the selected block, escape clears the selection, z undoes. Everything else is a button or a chip.

**Blocks and Windows.** Blocks judges the built blocks, the real ones or those of one synthetic set, at the settings in
use, a line at the top names them and links to Settings. Select these settings is for the real blocks only. Each block
gets a window count and a verdict listing every rule it breaks. The totals follow, and a row opens to compare the settings
in use with the ones its session was built with. Open a block to play it in metres over its environment, and Step through
its windows opens the Windows page, one window at a time with its checks.

**Synthetic.** Tick the built sessions to draw on, give a seed and the minutes of arena and track to make, and press
Generate. The generator fits a recipe to the real blocks of those sessions (speed, turn rate, pauses, runs per path, dwells,
how far from the centreline, how the head points against the speed, the distance to the arena's wall) and writes one
synthetic session in the transformed schema, with two LEDs in camera pixels. It goes through the same registration, cuts,
labels and windows as a real one, so its blocks have the real format. The set is named by its time and seed and keeps a
provenance file with the sources, the seed, the camera, the rules, the generator version and both recipes. Click a set to
lay its recipe beside the real one, a statistic a row. A set is a model and not data, Delete removes it whole.

**Real or synthetic.** Choose a set and a kind and press New pair. A real and a synthetic block of that kind show side by
side in a random order with a trail, playback and a speed trace, and no ids, runs or paths. Say which side is real. The
server reveals the answer, records the guess in the set's `guesses.json` and shows the set's tally. A tally near a half
means the synthetic blocks pass for real to the eye. It is a first check of the generator and not the validation of it.

**Outgoing.** The write path card gives where blocks are written with its status, the counts of reviews, blocks and built
sessions, and when the folder last changed. The selected card names the settings in `windows.json`. The Built card lists
per session the blocks built, the failed blocks with their problems, the sessions you excluded or the tool skipped, and
the settings it was built with, marked when they differ from the ones in use. A card for the synthetic folder counts its
sets, blocks and guesses. Rebuild all, on that card, builds the blocks of every reviewed session again from its review
after a confirmation, for when a rule changed. It builds at the selected settings when `windows.json` exists, else at the
settings in use, and never changes a review. The format of the processed files is folded at the bottom.

**Environments and About.** Environments draws every environment of `configs/environments/*.yaml` at one scale with its
parameters and, per built session, the registration it was given (scale, rotation, LED separation and offset, warnings).
It only reads. About gives the process, the rules the tool follows, what each action writes and, under Under the hood, the
internal routes. Nothing else is written, the transformed folder and the environments are only read.

## The export

    processed/
      review/{session_id}.json     the person's edits and notes, written whole on each save
      blocks/{block_id}.parquet    one built block, in metres at 60 Hz, one row per frame
      blocks.csv                   one row per built block
      metadata/{session_id}.json   what a build used, and per block its window count and verdict then
      windows.json                 the settings selected for export

    synthetic/
      sets/{set_id}/blocks/{block_id}.parquet   the set's blocks, the processed block format
      sets/{set_id}/blocks.csv                  one row per block
      sets/{set_id}/provenance.json             sources, seed, camera, rules, settings, generator version, both recipes
      sets/{set_id}/guesses.json                the quiz guesses, absent before the first

A block id is the session id, the epoch and a number within the epoch. A block's parquet holds `frame` (the lab frame
number), `t`, `x`, `y`, `heading`, `speed`, `turn_rate`, `n_lights`, the fill flags, `phase`, `trip`, `run`, `path_id`
and `clean`. `blocks.csv` holds the block's session, epoch, frames, duration, rate, run and trip counts, seconds of
heading lost, filled and held, status, reviewer, and the registration and kinematics version it was built under.
`windows.json` holds `settings`, `totals` (blocks, ok, trouble, windows, windows_ok at those settings), `selected_at`
and `selected_by`.

The RNN project reads these files and cuts the windows itself as `windows.json` says, so windows are never stored here.
Heading, phase and trip are for validation and analysis, not training inputs. A build writes a session's files under
temporary names and renames them in one short pass, so a failed build leaves the previous one whole. A block that fails a
check is not written and is listed under `failed` in the session's metadata. The Outgoing page reports leftover temporary
files, missing block files and orphan block files as problems of the processed folder. A set is written whole under a
temporary name and renamed, and never written twice.

The schema of every file and column is documented in [docs/architecture.md](docs/architecture.md), under Resources on
disk, and the running tool shows it: the processed and synthetic formats are folded at the bottom of Outgoing, the
incoming format at the bottom of Incoming, and `GET /api/format` gives all of them. The API and the page each carry a
format version, now 4, compared when the page loads. A change to the shape of any payload (a key added, removed or
reshaped in a route's answer) bumps both in the same commit, so a page served against an older process says "restart the
API" and does not fail on a missing key.

## Testing

    pixi run ratreplay-test       # pytest on the backend, then Vitest on the frontend
    pixi run ratreplay-ui         # Vite with hot reload, /api proxied to port 8060 (run the API too)

    backend/tests/unit/           the engines, accesses and utilities, and the import layering of the backend
    backend/tests/integration/    one file per manager, real accesses over synthetic folders, no HTTP
    backend/tests/system/         the flows through the HTTP client: save, rebuild, readiness, select, health, refusals, synthetic sets
    frontend/tests/              Vitest on the pure TypeScript: geometry, the editor, keys, formats, the page views
    frontend/e2e/                Playwright flows in a real browser, against the built frontend

Every test uses synthetic folders, never real data and never `configs/local.yaml`. The four Playwright flows are: review a
session, refuse a split, split, save, then exclude and include it (`review.spec.ts`), set the window settings, read the
verdicts, step the windows and select the settings (`readiness.spec.ts`), a config missing a key, Reload, Rebuild all,
Environments and About (`folders.spec.ts`), and generate a synthetic set, compare its recipe, find it on Blocks and
Outgoing and delete it (`synthetic.spec.ts`). They need the build first and a one time browser install:

    pixi run -e ratreplay npm --prefix ratreplay/frontend exec -- playwright install chromium   # once
    pixi run ratreplay-build
    pixi run -e ratreplay npm --prefix ratreplay/frontend run e2e

After a change to the `packages` list in `pyproject.toml`, run `pixi reinstall axis-of-travel-rnn` once.

## More

The design is in [docs/architecture.md](docs/architecture.md), the order of the rebuild, the notes from building it and the
debrief in [docs/plan.md](docs/plan.md), the tasks and the findings from use (K1 to K39, the open ones marked) in
[docs/tasks.md](docs/tasks.md), the API as built in [backend/README.md](backend/README.md). Two open items change what is
built: a short tracking loss inside a block drops the block (K31) and the registration of a synthetic session of real width
can miss a corridor peak (K37).
