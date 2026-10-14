"""
The funnel on the synthetic tables: the surviving epochs, the count after each step, --only, and the block cuts.
"""

import numpy as np

from process_lab_data import select

from .conftest import MAX_GAP, RATE_HZ, S1, S6

# A scripted session of 3000 frames with the epoch at 301 to 2700: a pause at 1201 and another at 2650, an unfilled
# stretch of exactly max_gap frames at 700 to 729 that stays inside its block, and one of 50 frames at 1850 to 1899
# that cuts. The stretch after the second pause is 51 frames, under MIN_BLOCK_S.
SCRIPTED_EPOCH = {"frame_start": 301, "frame_end": 2700}
SCRIPTED_CUTS = [(301, 1200), (1201, 1849), (1900, 2649), (2650, 2700)]


def scripted_frames():
    """
    The scripted session as the arrays cut_blocks reads.
    """
    frame = np.arange(1, 3001)
    t = (frame - 1) / RATE_HZ
    t[frame >= 1201] += 120.0
    t[frame >= 2650] += 7.0
    unfilled_front, unfilled_back = np.zeros(3000, bool), np.zeros(3000, bool)
    unfilled_front[699:729] = True  # both lights lost for exactly max_gap frames: stays
    unfilled_back[699:729] = True
    unfilled_front[999:1049] = True  # one light lost for 50 frames: stays under the both rule
    unfilled_front[1849:1899] = True  # both lights lost for 50 frames: cuts
    unfilled_back[1849:1899] = True
    return {"frame": frame, "t": t, "unfilled_front": unfilled_front, "unfilled_back": unfilled_back}


def test_blocks_are_cut_at_pauses_long_both_lights_lost_stretches_and_the_epoch_bounds_then_short_ones_dropped():
    frames = scripted_frames()
    assert select.cut_at(frames, SCRIPTED_EPOCH, MAX_GAP) == SCRIPTED_CUTS
    assert select.cut_blocks(frames, SCRIPTED_EPOCH, MAX_GAP, RATE_HZ) == SCRIPTED_CUTS[:3]


def test_blocks_of_reads_the_frames_and_counts_before_and_after_the_length_rule(transformed):
    tables = select.read_tables(transformed)
    epochs, _ = select.funnel(tables, None)
    blocks, counts = select.blocks_of(transformed, epochs, tables["sessions"])
    assert [(b["block_id"], b["frame_start"], b["frame_end"], b["n_frames"], b["duration_s"]) for b in blocks] == [
        (f"{S1}_arena_01", 1, 600, 600, 10.0), (f"{S1}_track_01", 601, 1200, 600, 10.0)]
    assert blocks[1]["environment"] == "triple_t"
    assert counts == [("blocks, cut at pauses and gaps", 4), ("blocks, at least 10 s", 2),
                      ("blocks, kind arena", 1), ("blocks, kind track", 1)]


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
