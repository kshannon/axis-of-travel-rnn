"""
What the routes share: the settings path of the app and the data folders its config names.
"""

from fastapi import Depends, Request

from proj_helpers import paths

from ..managers import sources


def settings_path(request: Request):
    """
    The window settings file of the app.
    """
    return request.app.state.settings_path


def config_path(request: Request):
    """
    The config file the data folders come from.
    """
    return str(request.app.state.config_path)


def current_config(request: Request):
    """
    The config the data folders come from.
    """
    return request.app.state.config


def reread_config(request: Request, reload: bool = False):
    """
    The config, read from its file again first when the query says reload=true.
    """
    if reload:
        request.app.state.config = paths.local_config(request.app.state.config_path)
    return request.app.state.config


def transformed_root(config=Depends(current_config), file=Depends(config_path)):
    """
    The transformed folder, which every session route reads.
    """
    return sources.transformed_root(config, file)


def processed_root(config=Depends(current_config), file=Depends(config_path)):
    """
    The processed folder, which holds the reviews and the blocks.
    """
    return sources.required_root(config, file, "processed")
