"""
The readers: the lab's file names become sessions with skips and selection, and each MATLAB file kind, classic and v7.3, reads to the same values, a missing variable named, a cell array dereferenced.
"""

from datetime import date

import numpy as np
import pytest

from transform_lab_data.transform_helpers import checks
from transform_lab_data.transform_helpers.orchestrator import Record
from transform_lab_data.transform_helpers.readers import Session, catalog, read, select

from .synthetic_mat import example_session, session_names, write_session

FORMATS = ("classic", "v7.3")


def written(folder, variables, fmt):
    """
    The record of the variables written to folder as one session's file pair in this MATLAB format, read.
    """
    dvt, rmaps = session_names("NS14", 27, "021915", "001")
    write_session(folder, variables, (dvt, rmaps), fmt)
    session = Session(session_id="NS14_rec27_20150219_001", subject_id="NS14", group="NS14Data", session="001", rec=27,
                      date=date(2015, 2, 19), tag=None, tag_raw=None, dvt_path=folder / dvt, rmaps_path=folder / rmaps)
    return read(Record(session))


def test_names_become_sessions_with_skips_and_selection(tmp_path):
    lab = tmp_path / "lab"
    two_tags_dvt = session_names("NS15", 7, "110315", "001")[0]
    two_tags_rmaps = "NS15_rec7_110315001_tt_dark_rmaps_plus45.mat"
    doubled = [*session_names("NS15", 6, "110315", "001"), session_names("NS15", 6, "110315", "001", "plus45")[1]]
    folders = {
        "JL1HPCData": session_names("JL1", 3, "110315", "001"),
        "NS14Data": [*session_names("NS14", 1, "021915", "001"),
                     *session_names("NS14", 2, "021815", "001", "Dark"),
                     *session_names("NS14", 10, "030115", "001", "plus45turn", tag_first=True),
                     "allPLXFiles.mat"],
        "NS15Data": [two_tags_dvt, two_tags_rmaps, *doubled],
    }
    for group, names in folders.items():
        (lab / group).mkdir(parents=True)
        for name in names:
            (lab / group / name).touch()

    sessions, skipped = catalog(lab)

    # rec2 before rec10, which a sort of the ids as text would get wrong
    ids = ["JL1_rec3_20151103_001", "NS14_rec1_20150219_001", "NS14_rec2_20150218_001", "NS14_rec10_20150301_001"]
    assert [s.session_id for s in sessions] == ids
    assert [(s.group, s.tag, s.tag_raw) for s in sessions] == [
        ("JL1HPCData", None, None), ("NS14Data", None, None), ("NS14Data", "dark", "Dark"),
        ("NS14Data", "plus45turn", "plus45turn")]
    assert skipped == sorted([("allPLXFiles.mat", "does not parse"), (two_tags_rmaps, "does not parse"),
                              (two_tags_dvt, "no twin"), *[(name, "doubled file") for name in doubled]])

    def chosen(only, sample):
        return [s.session_id for s in select(sessions, only, sample)]

    assert chosen("NS14_rec1", None) == [ids[1]]
    assert chosen("NS14", None) == ids[1:]
    assert chosen(None, 1) == ids[:2]
    assert chosen("NS14", 2) == ids[1:3]


@pytest.mark.parametrize("fmt", FORMATS)
def test_a_missing_variable_is_named_by_the_input_check(tmp_path, fmt):
    variables = example_session()
    del variables["HDRadians"]
    record = checks.check_inputs(written(tmp_path, variables, fmt))
    assert checks.failed(record.results) == ["variables_present"]
    assert record.results["variables_present"]["detail"]["missing"] == ["HDRadians"]


def test_the_transposed_v73_layout_reads_the_same_as_the_classic_one_with_its_cells_dereferenced(tmp_path):
    classic, v73 = (written(tmp_path / fmt, example_session(), fmt) for fmt in FORMATS)
    assert v73.trk["processedDVT"].shape == classic.trk["processedDVT"].shape == (900, 10)  # not the (10, 900) on disk
    markers = v73.ana["runPosMarkers"]
    assert all(isinstance(x, np.ndarray) and x.dtype == float for pair in markers for x in pair)  # no h5py reference left
    for got in ("trk", "ana"):
        a, b = getattr(classic, got), getattr(v73, got)
        assert set(a) == set(b)
        for name in a:
            np.testing.assert_equal(b[name], a[name], err_msg=name)
