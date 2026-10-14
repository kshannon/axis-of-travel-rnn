"""
The app on the synthetic folders: a corrupt block names its error, the table pager chooses nothing, the strip's bars.
"""

from view_lab_data import app, data

from .conftest import SESSION


def test_a_corrupt_block_starts_the_app_and_carries_its_error_to_the_figure(processed):
    (processed / "track" / "blocks" / f"{SESSION}_track_1.parquet").write_bytes(b"garbage")
    assert app.make_app(processed, False).layout is not None
    block = data.list_blocks(processed, False)[0]
    assert app.block_runs(processed, False, block) == []
    payload = app.block_payload(processed, False, block, [])
    assert payload["block_id"] == block["block_id"] and payload["error"].startswith("ArrowInvalid")


def test_the_table_pager_clearing_the_active_cell_chooses_nothing(transformed):
    blocks = data.list_blocks(transformed, True)
    runs = {b["block_id"]: data.list_runs(transformed, True, b) for b in blocks}
    targets = [(b["block_id"], None) for b in blocks]
    track = blocks[1]["block_id"]
    assert app.choose("table", SESSION, track, 1, 0, None, blocks, runs, targets) is None
    assert app.choose("table", SESSION, track, 1, 0, {"row_id": f"{track}|2"}, blocks, runs, targets) == (track, 2)


def test_the_strip_has_one_bar_per_run_coloured_by_path_and_hatched_when_dirty(transformed):
    block = data.list_blocks(transformed, True)[1]
    runs = data.list_runs(transformed, True, block)
    runs.append({**runs[0], "run": 3, "start": 450, "end": 509, "duration_s": 1.0})
    strip = app.strip_figure(runs, 600)
    bars = [trace for trace in strip["data"] if trace["type"] == "bar"]
    assert [(bar["base"][0], bar["x"][0]) for bar in bars] == [(99 / 60, 121 / 60), (299 / 60, 101 / 60), (7.5, 1.0)]
    assert [bar["marker"]["pattern"]["shape"] for bar in bars] == ["", app.DIRTY_PATTERN, ""]
    assert bars[0]["marker"]["color"] == bars[2]["marker"]["color"] != bars[1]["marker"]["color"]
    assert [bar["showlegend"] for bar in bars] == [True, True, False]
    hover = strip["data"][0]
    assert hover["text"][0] == "between runs" and hover["text"][20] == "run 1, path 3, clean"
    assert strip["layout"]["xaxis"]["range"] == [0, 10]
