"""
The FastAPI app: the routes under /api and the built frontend at /.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from proj_helpers import paths

from .access.environment import EnvironmentAccess
from .access.processed import ProcessedAccess
from .access.transformed import TransformedAccess
from .engines.trajectory import TrajectoryEngine
from .managers.review import ReviewManager
from .utilities import version
from .utilities.errors import Invalid, NotFound
from .routers import blocks, data_format, review, sources, windows
from .stores.data_sources import DataSources

# The frontend is served once it has been built.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ROUTERS = (data_format.router, sources.router, review.router, blocks.router, windows.router)
INVALID = 400
UNPROCESSABLE = 422


def review_manager(data_sources, code_version):
    """
    The ReviewManager over the folders the config names now, Invalid or NotFound as the sources say when a folder is not there. The components hold no state, so one is built for each request and Reload takes effect at once.
    """
    return ReviewManager(TrajectoryEngine(), TransformedAccess(data_sources.transformed_root()), ProcessedAccess(data_sources.processed_root()),
                         EnvironmentAccess(paths.environments_dir()), code_version)


def create_app(config_path=None, settings_path=None):
    """
    The app with its routers mounted and the built frontend at /, the data folders from the config file at config_path (configs/local.yaml when none is given, read at start and on reload) and the window settings file at settings_path.
    """
    app = FastAPI(title="RatReplay", openapi_url="/api/openapi.json", docs_url=None, redoc_url=None)
    app.state.sources = DataSources(config_path, settings_path)
    code_version = version.git_commit(paths.repo_root())
    app.state.review = lambda: review_manager(app.state.sources, code_version)

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
