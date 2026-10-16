"""
The FastAPI app: the routes under /api and the built frontend at /.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from axis_of_travel_rnn.windows import CONFIG

from .errors import Invalid, NotFound
from .routers import blocks, data_format, review, sessions, sources, windows

# The sources registry lives in the home folder, outside the repository, and the window settings file is the one the
# training pipeline reads. The frontend is served once it has been built.
DEFAULT_REGISTRY = Path.home() / ".ratreplay" / "sources.json"
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ROUTERS = (data_format.router, sources.router, sessions.router, review.router, blocks.router, windows.router)
INVALID = 400
UNPROCESSABLE = 422


def create_app(registry_path=None, settings_path=None):
    """
    The app with its routers mounted and the built frontend at /, the sources registry at registry_path and the window settings file at settings_path.
    """
    app = FastAPI(title="RatReplay", openapi_url="/api/openapi.json", docs_url=None, redoc_url=None)
    app.state.registry_path = Path(registry_path) if registry_path else DEFAULT_REGISTRY
    app.state.settings_path = Path(settings_path) if settings_path else CONFIG

    @app.exception_handler(HTTPException)
    def http_error(request, error):
        """
        Every error leaves as {"error": text}.
        """
        return JSONResponse({"error": error.detail}, status_code=error.status_code)

    @app.exception_handler(NotFound)
    def not_found(request, error):
        """
        An unknown id or file is a 404.
        """
        return JSONResponse({"error": str(error)}, status_code=404)

    @app.exception_handler(Invalid)
    def invalid(request, error):
        """
        A request that cannot be served is a 400.
        """
        return JSONResponse({"error": str(error)}, status_code=INVALID)

    @app.exception_handler(RequestValidationError)
    def bad_request(request, error):
        """
        A body or query that fails its schema is a 422 naming the first field.
        """
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"][1:])
        return JSONResponse({"error": f"{where}: {first['msg']}" if where else first["msg"]}, status_code=UNPROCESSABLE)

    for router in ROUTERS:
        app.include_router(router)
    if FRONTEND_DIST.is_dir():  # last, so the routes above win
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
