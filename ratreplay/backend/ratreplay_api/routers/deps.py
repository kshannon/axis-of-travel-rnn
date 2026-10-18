"""
What the routes share: the two managers the composition root built, kept on the app, and the config file they were built from.
"""

from fastapi import Request


def review_manager(request: Request):
    """
    The ReviewManager the app was built with.
    """
    return request.app.state.review


def validation_manager(request: Request):
    """
    The ValidationManager the app was built with.
    """
    return request.app.state.validation


def config_path(request: Request):
    """
    The config file the folders come from.
    """
    return request.app.state.config.path


def reread_validation_manager(request: Request, reload: bool = False):
    """
    The ValidationManager, rebuilt with the rest from the config file read again first when the query says reload=true.
    """
    state = request.app.state
    if reload:
        state.config.reload()
        state.build(state.config)
    return state.validation
