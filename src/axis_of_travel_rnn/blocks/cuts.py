"""
Where a session is cut into blocks, from its frames and the rules: pauses, jumps, long tracking gaps and epoch bounds, the margins trimmed beside them and the blocks left.
"""

import numpy as np

# The reason a cut point carries, the status and note of a block before any edit, and what each value of the gap_lights
# rule means: "either" cuts when one light is lost, "both" only when both are.
PAUSE, GAP, JUMP, EPOCH = "pause", "gap", "jump", "epoch"
INITIAL_STATUS, INITIAL_NOTE = "auto", None
LOST = {"either": np.logical_or, "both": np.logical_and}


def selected(epochs, rules):
    """
    The epochs the rules cut into blocks: the kinds the rules name under their condition.
    """
    return [e for e in epochs if e["epoch"] in rules["epochs"] and e["condition"] == rules["condition"]]


def runs_of(mask):
    """
    The (first, stop) index pairs of every stretch where the mask is true.
    """
    edges = np.flatnonzero(np.diff(np.concatenate(([False], mask, [False])).astype(np.int8)))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


def spans(frame, mask):
    """
    The (first, last) 1-based frame pairs of every stretch where the mask is true.
    """
    return [(int(frame[first]), int(frame[stop - 1])) for first, stop in runs_of(mask)]


def inside(frames, epoch):
    """
    True on the frames of the epoch.
    """
    return (frames["frame"] >= epoch["frame_start"]) & (frames["frame"] <= epoch["frame_end"])


def epoch_index(frames, epochs):
    """
    The position in epochs of the epoch holding each frame, minus one for a frame in none.
    """
    index = np.full(len(frames["frame"]), -1)
    for i, epoch in enumerate(epochs):
        index[inside(frames, epoch)] = i
    return index


def pauses(t, rules):
    """
    True on the first frame after a step in t over pause_step_s.
    """
    return np.concatenate(([False], np.diff(t) > rules["pause_step_s"]))


def jumps(frames, rules):
    """
    True on the frame whose mashup position moved over jump_px from the frame before within one normal step, never across a pause.
    """
    step = np.hypot(np.diff(frames["mashup_x"]), np.diff(frames["mashup_y"]))
    return np.concatenate(([False], (step > rules["jump_px"]) & (np.diff(frames["t"]) <= rules["pause_step_s"])))


def gaps(frames, max_gap, rules):
    """
    True on every frame of a stretch with the gap_lights lights unfilled for more than max_gap frames.
    """
    unfilled = LOST[rules["gap_lights"]](frames["unfilled_front"], frames["unfilled_back"])
    gap = np.zeros(len(unfilled), bool)
    for first, stop in runs_of(unfilled):
        if stop - first > max_gap:
            gap[first:stop] = True
    return gap


def handled(cut, first, last):
    """
    Whether a cut lies between each stretch and the one before it, and the one after it, the epoch bounds counting as cuts.
    """
    between = [bool(cut[a + 1:b + 1].any()) for a, b in zip(last[:-1], first[1:])]
    return np.array([True] + between, bool), np.array(between + [True], bool)


def stretches(frames, epoch, max_gap, rate_hz, rules):
    """
    The epoch's stretches as four index arrays, first and last before the margins then after, a vanished stretch having first over last.
    """
    cut = pauses(frames["t"], rules) | jumps(frames, rules)
    cut_next = np.concatenate((cut[1:], [False]))
    kept = inside(frames, epoch) & ~gaps(frames, max_gap, rules)
    before = np.concatenate(([False], kept[:-1]))
    after = np.concatenate((kept[1:], [False]))
    first = np.flatnonzero(kept & (~before | cut))
    last = np.flatnonzero(kept & (~after | cut_next))
    margin = round(rules["pause_margin_s"] * rate_hz)
    handled_first, handled_last = handled(cut, first, last)
    return first, last, first + margin * handled_first, last - margin * handled_last


def cut_epoch(frames, epoch, max_gap, rate_hz, rules):
    """
    The epoch's stretches with the margins trimmed, and the frames trimmed from them as margins, both as 1-based inclusive frame pairs.
    """
    frame, margins = frames["frame"], []
    first, last, trimmed_first, trimmed_last = stretches(frames, epoch, max_gap, rate_hz, rules)
    for a, b, trimmed_a, trimmed_b in zip(first, last, trimmed_first, trimmed_last):
        if trimmed_a > trimmed_b:
            margins.append((int(frame[a]), int(frame[b])))
            continue
        if trimmed_a > a:
            margins.append((int(frame[a]), int(frame[trimmed_a - 1])))
        if trimmed_b < b:
            margins.append((int(frame[trimmed_b + 1]), int(frame[b])))
    kept = trimmed_first <= trimmed_last
    return list(zip(frame[trimmed_first[kept]].tolist(), frame[trimmed_last[kept]].tolist())), margins


def cut_points(frames, epochs, max_gap, rules):
    """
    What cut the epochs, by frame and reason: each epoch start, pause, jump and gap start (a gap with its last frame), in frame order.
    """
    frame, points = frames["frame"], []
    pause, jump, gap = pauses(frames["t"], rules), jumps(frames, rules), gaps(frames, max_gap, rules)
    for epoch in epochs:
        here = inside(frames, epoch)
        points.append({"frame": epoch["frame_start"], "reason": EPOCH})
        points += [{"frame": f, "reason": PAUSE} for f in frame[pause & here].tolist()]
        points += [{"frame": f, "reason": JUMP} for f in frame[jump & here].tolist()]
        points += [{"frame": a, "frame_end": b, "reason": GAP} for a, b in spans(frame, gap & here)]
    return sorted(points, key=lambda p: (p["frame"], p["reason"]))


def stretch_rows(epochs, pieces):
    """
    Every stretch left after the margins, short ones included, with its epoch: the range a block edge may move within.
    """
    return [{"epoch": e["epoch"], "frame_start": a, "frame_end": b} for e, found in zip(epochs, pieces) for a, b in found]


def initial_blocks(session_id, epochs, pieces, rate_hz, rules):
    """
    The blocks the rules make before any edit: the stretches of at least min_block_s, numbered within their epoch.
    """
    blocks = []
    for epoch, found in zip(epochs, pieces):
        long = [(a, b) for a, b in found if b - a + 1 >= rules["min_block_s"] * rate_hz]
        blocks += [{"block_id": f"{session_id}_{epoch['epoch']}_{i:02d}", "epoch": epoch["epoch"], "environment": epoch["environment"],
                    "frame_start": a, "frame_end": b, "status": INITIAL_STATUS, "note": INITIAL_NOTE}
                   for i, (a, b) in enumerate(long, 1)]
    return blocks
