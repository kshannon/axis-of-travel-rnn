"""
The three failures a request can end in, turned into 404, 400 and 409 by the app.
"""


class NotFound(Exception):
    """
    An id or file that does not exist.
    """


class Invalid(Exception):
    """
    A request that cannot be served as asked.
    """


class Conflict(Exception):
    """
    A request that contradicts what is recorded.
    """
