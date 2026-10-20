"""
The Arrow encoding of a session's arrays.
"""

import numpy as np
import pyarrow as pa

from ratreplay_api.utilities import arrow


def test_arrays_round_trip_with_their_dtypes_and_nan_kept():
    arrays = {"x": np.array([1.5, np.nan, 3.0]), "n_lights": np.array([2, 1, 0], np.int8), "filled": np.array([True, False, True])}
    table = pa.ipc.open_stream(arrow.encode(arrays)).read_all()
    assert table.schema.types == [pa.float64(), pa.int8(), pa.bool_()]
    assert np.isnan(table["x"].to_numpy()[1]) and table["x"].null_count == 0
    assert table["n_lights"].to_pylist() == [2, 1, 0]
    assert table["filled"].to_pylist() == [True, False, True]
