"""
Arrays to Arrow IPC stream bytes, what the browser reads for a session or a block.
"""

import pyarrow as pa
from fastapi import Response

MEDIA_TYPE = "application/vnd.apache.arrow.stream"


class ArrowResponse(Response):
    """
    A response of Arrow bytes, which names its media type in the OpenAPI schema too.
    """

    media_type = MEDIA_TYPE


def encode(arrays):
    """
    A dict of equal length numpy arrays as one Arrow IPC stream, each column in its own dtype and NaN kept as NaN.
    """
    table = pa.table({name: pa.array(values) for name, values in arrays.items()})
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()
