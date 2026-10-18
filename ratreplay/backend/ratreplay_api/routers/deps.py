"""
What the routes share: the DataSources of the app and the managers built over them.
"""

from fastapi import Request


def data_sources(request: Request):
    """
    The DataSources of the app, which tell the routes the config file the folders come from.
    """
    return request.app.state.sources


def review_manager(request: Request):
    """
    The ReviewManager over the folders the config names now.
    """
    return request.app.state.review()


def validation_manager(request: Request):
    """
    The ValidationManager over the folders the config names now.
    """
    return request.app.state.validation()


def reread_validation_manager(request: Request, reload: bool = False):
    """
    The ValidationManager, with the config file read again first when the query says reload=true.
    """
    if reload:
        request.app.state.sources.reload()
    return request.app.state.validation()
