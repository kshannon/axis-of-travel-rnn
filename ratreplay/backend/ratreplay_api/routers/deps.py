"""
What the routes share: the DataSources of the app and the ReviewManager built over them.
"""

from fastapi import Depends, Request


def data_sources(request: Request):
    """
    The DataSources of the app, which the managers hand on to the stores to ask where the data is.
    """
    return request.app.state.sources


def reread_sources(reload: bool = False, sources=Depends(data_sources)):
    """
    The DataSources, with the config file read again first when the query says reload=true.
    """
    if reload:
        sources.reload()
    return sources


def review_manager(request: Request):
    """
    The ReviewManager over the folders the config names now.
    """
    return request.app.state.review()
