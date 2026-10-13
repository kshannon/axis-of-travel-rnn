"""
The finding half of readers: the lab's file names become sessions, with skips and selection.
"""

from lab_data_transform.transform_helpers.readers import catalog, select

from .synthetic_mat import session_names


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
