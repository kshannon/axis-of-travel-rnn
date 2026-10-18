"""
The composition root: the config read once, the engine, the accesses and the two managers built once from it, the routes under /api and the built frontend at /.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .access.environment import EnvironmentAccess
from .access.processed import ProcessedAccess
from .access.transformed import TransformedAccess
from .engines.trajectory import TrajectoryEngine
from .managers.review import ReviewManager
from .managers.validation import ValidationManager
from .routers import review, validation
from .utilities import version
from .utilities.config import Config
from .utilities.errors import Invalid, NotFound

# The frontend is served once it has been built.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_CONFIG = REPO_ROOT / "configs" / "local.yaml"
ENVIRONMENTS = REPO_ROOT / "configs" / "environments"  # becomes a config key when the tool leaves the repository
# The config keys that name the two data folders, known here and nowhere else.
TRANSFORMED_KEY, PROCESSED_KEY = "TRANSFORMED_LAB_DATA", "PROCESSED_LAB_DATA"
ROUTERS = (review.router, validation.router)
NOT_FOUND = 404
INVALID = 400
UNPROCESSABLE = 422


class UnsetAccess:
    """
    Stands in for the access of a folder the config does not name: its health says so, its schema is its format's as ever, and every verb that reads or writes the folder refuses with the problem.
    """

    def __init__(self, problem, access):
        self.problem, self.access = problem, access(None)

    def health(self):
        """
        The health of a folder that is not named: the problem alone.
        """
        return {"root": None, "exists": False, "problems": [self.problem], "counts": {}, "manifest": None}

    def schema(self):
        """
        The schema of the access class, a fact of its format that needs no folder.
        """
        return self.access.schema()

    def refused(self, *args):
        """
        A verb that needs the folder, refused with the problem.
        """
        raise Invalid(self.problem)

    # The verbs of TransformedAccess and ProcessedAccess that need their folder.
    sessions = session = refused
    reviews = review = write_review = refused
    blocks = block = built = metadata = write_blocks = refused
    window_settings = write_window_settings = refused


def access_over(config, key, access):
    """
    The access over the folder the config names under the key, or the stand-in that says the key is not set.
    """
    try:
        root = config.value(key)
    except Invalid as error:
        return UnsetAccess(str(error), access)
    return access(root)


def create_app(config_path=None):
    """
    The app with its components built once from the config file at config_path (configs/local.yaml when none is given), its routers mounted and the built frontend at /.
    """
    app = FastAPI(title="RatReplay", openapi_url="/api/openapi.json", docs_url=None, redoc_url=None)
    app.state.config = Config(config_path or LOCAL_CONFIG)
    code_version = version.git_commit(REPO_ROOT)

    def build(config):
        """
        Build the engine, the accesses and the two managers from the config and keep the managers on the app, which is how Reload takes effect.
        """
        trajectory = TrajectoryEngine()
        transformed = access_over(config, TRANSFORMED_KEY, TransformedAccess)
        processed = access_over(config, PROCESSED_KEY, ProcessedAccess)
        environment = EnvironmentAccess(ENVIRONMENTS)
        app.state.review = ReviewManager(trajectory, transformed, processed, environment, code_version)
        app.state.validation = ValidationManager(trajectory, transformed, processed, environment)

    app.state.build = build
    build(app.state.config)

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
        return JSONResponse({"error": str(error)}, status_code=NOT_FOUND)

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
