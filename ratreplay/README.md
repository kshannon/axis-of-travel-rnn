# RatReplay

A standalone review tool for rat trajectory data: attach data folders in a known format, replay
sessions, confirm the blocks a processor will build, inspect built blocks and training windows.
Localhost only. It lives here with its own backend and frontend so it can become its own
repository. The old Dash tool in `src/ratreplay/` stays until this one reaches parity.

The design, layering, API, pages and testing plan are in [docs/architecture.md](docs/architecture.md).

## Run

Node comes from pixi through the `ratreplay` environment, `pixi run` finds it for the tasks below.

    pixi run ratreplay-install    # once: the frontend's npm packages
    pixi run ratreplay-build      # the frontend into ratreplay/frontend/dist
    pixi run ratreplay-api        # http://127.0.0.1:8060, the API and the built frontend (--port N)
    pixi run ratreplay-ui         # while developing: Vite with hot reload, /api proxied to port 8060
    pixi run ratreplay-test       # pytest on the backend, then vitest on the frontend

The Playwright flows run against the built frontend served by the API:

    pixi run -e ratreplay npm --prefix ratreplay/frontend exec -- playwright install chromium   # once
    pixi run -e ratreplay npm --prefix ratreplay/frontend run e2e

The backend imports the project packages, so after pulling a change to the `packages` list in
`pyproject.toml` run `pixi reinstall axis-of-travel-rnn` once.

## Layout

    backend/ratreplay_api/   FastAPI: routers, managers, engines, stores
    backend/tests/           pytest on synthetic folders, the API through the test client
    frontend/                Vite, TypeScript, Alpine, D3 and Tailwind: pages, drawing, the typed API client
    docs/architecture.md     the design the code is reviewed against
