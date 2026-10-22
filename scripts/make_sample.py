"""
Build tests/fixtures/sample/ from the block tests' synthetic fixture sessions with the sample blueprint, run as pixi run python scripts/make_sample.py.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # the tests package holds the fixture

import axis_of_travel_rnn.blocks.__main__ as entry  # noqa: E402
from axis_of_travel_rnn.blocks.blueprint import blueprint_path, read_blueprint  # noqa: E402
from tests.unit.blocks.fixtures import S1, S4, S6, frames_table, write_transformed  # noqa: E402
from tests.unit.blocks.test_build import accepted_review  # noqa: E402

BLUEPRINT = "sample"
SAMPLE = REPO / "tests" / "fixtures" / "sample"  # the one folder in the repository this script writes
# S4 has no frames in the fixture, so the script writes them, and its track block is dropped in its review because the
# build refuses it (position not finite on every frame). S1 gives an arena and a track block, S4 an arena block, S6 a track block.
EXTRA_FRAMES = S4
DROPPED = {S4: "track"}


def review(transformed, sid):
    """
    The fixture's accepted review of the session, the block of its dropped epoch marked dropped.
    """
    found = accepted_review(transformed, sid)
    for block in found["blocks"]:
        if DROPPED.get(sid) == block["epoch"]:
            block["status"] = "dropped"
    return found


def main():
    """
    Write the fixture's transformed folder and reviews to a temporary folder, build the sample there, replace tests/fixtures/sample with it and print its data id.
    """
    path = blueprint_path(BLUEPRINT)
    blueprint = read_blueprint(path)
    with tempfile.TemporaryDirectory() as tmp:
        transformed, reviews, out = Path(tmp) / "transformed", Path(tmp) / "reviews", Path(tmp) / BLUEPRINT
        write_transformed(transformed)
        pq.write_table(frames_table(EXTRA_FRAMES, (), (), ()), transformed / "frames" / f"{EXTRA_FRAMES}.parquet")
        reviews.mkdir()
        for sid in blueprint.sessions:
            (reviews / f"{sid}.json").write_text(json.dumps(review(transformed, sid)))
        manifest = entry.build(blueprint, entry.sha256_of(path), transformed, reviews, out)
        if SAMPLE.exists():
            shutil.rmtree(SAMPLE)
        shutil.copytree(out, SAMPLE)
    print(f"data id {manifest['data_id']} in {SAMPLE}")
    if blueprint.expected_data_id not in (None, manifest["data_id"]):
        print(f"make_sample: data id differs from the blueprint's expected {blueprint.expected_data_id}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
