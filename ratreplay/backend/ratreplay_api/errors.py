"""
The two failures a request can end in, turned into 404 and 400 by the app.
"""


class NotFound(Exception):
    """
    An id or file that does not exist.
    """


class Invalid(Exception):
    """
    A request that cannot be served as asked.
    """
