"""
What the routes share: the registry and settings paths of the app, and the source a path names.
"""

from fastapi import Depends, Request

from .. import registry
from ..errors import Invalid


def registry_path(request: Request):
    """
    The sources file of the app.
    """
    return request.app.state.registry_path


def settings_path(request: Request):
    """
    The window settings file of the app.
    """
    return request.app.state.settings_path


def attached_source(sid: str, path=Depends(registry_path)):
    """
    The attached source with the id in the path.
    """
    return registry.get(path, sid)


def transformed_source(source=Depends(attached_source)):
    """
    The attached source, which must hold sessions.
    """
    if source["kind"] != "transformed":
        raise Invalid(f"source {source['id']} is {source['kind']}, sessions need a transformed source")
    return source
