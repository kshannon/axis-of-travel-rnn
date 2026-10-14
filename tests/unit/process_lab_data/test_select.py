"""
The funnel on the synthetic tables: the surviving epochs, the count after each step and --only.
"""

from process_lab_data import select

from .conftest import S1, S6


def test_the_funnel_keeps_the_baseline_arena_and_track_epochs_of_standard_included_sessions(transformed):
    epochs, counts = select.funnel(select.read_tables(transformed), None)
    assert [(e["session_id"], e["epoch"]) for e in epochs] == [(S1, "arena"), (S1, "track"), (S6, "track")]
    assert [count for _, count in counts] == [6, 4, 3, 2, 2, 5, 4, 3, 4, 3]
    assert [step for step, _ in counts] == [
        "sessions, all sessions", "sessions, protocol standard", "sessions, group allowed",
        "sessions, not excluded by annotations", "sessions, --only",
        "epochs, of those sessions", "epochs, kind arena or track", "epochs, condition baseline",
        "runs, of surviving track epochs", "runs, clean",
    ]


def test_only_matches_the_whole_id_or_a_prefix_ending_at_an_underscore(transformed):
    tables = select.read_tables(transformed)
    for only, kept in (("NS16", [S6]), (S6, [S6]), ("NS14_rec1", [S1]), ("NS1", [])):
        epochs, counts = select.funnel(tables, only)
        assert sorted({e["session_id"] for e in epochs}) == kept
        assert dict(counts)["sessions, --only"] == len(kept)


def test_missing_annotations_and_verdicts_exclude_nothing(transformed):
    (transformed / select.ANNOTATIONS).unlink()
    tables = select.read_tables(transformed)
    assert tables["annotations"] == [] and tables["verdicts"] == []
    _, counts = select.funnel(tables, None)
    assert dict(counts)["sessions, not excluded by annotations"] == 3
