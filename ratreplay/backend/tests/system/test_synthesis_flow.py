"""
The synthetic flow of the HTTP surface over the synthetic folders: a set generated from the built sessions, listed, read, judged and found by block id, quizzed and tallied, deleted, and the refusals. Status codes, shapes and the sequence of calls, the numbers are proven below this level.
"""

import io

import pyarrow as pa
import pytest
from fixtures import S1, S2, S6

from ratreplay_api.managers.synthesis import QUIZ_COLUMNS, QUIZ_ROW_KEYS
from ratreplay_api.utilities.arrow import MEDIA_TYPE

SHORT = {"window_s": 5}
ACCEPT = [{"op": "accept"}]
GENERATE = {"sources": [S1, S6], "seed": 3, "length_s": {"arena": 20.0, "track": 60.0}, "settings": SHORT}
HEADER_KEYS = {"row", "rate_hz", "geometry"}
SIDES = ("left", "right")


def table_of(response):
    """
    The Arrow table in the bytes of a response.
    """
    return pa.ipc.open_stream(io.BytesIO(response.content)).read_all()


@pytest.fixture
def built(client):
    """
    The client after S1 and S6 were reviewed and built through the API.
    """
    for sid in (S1, S6):
        assert client.put(f"/api/sessions/{sid}/blocks", json={"edits": ACCEPT, "notes": "", "settings": SHORT, "start_offset_m": None}).status_code == 200
    return client


def test_a_set_is_generated_listed_read_judged_quizzed_tallied_and_deleted_through_the_api(built, synthetic):
    assert built.get("/api/sets").json() == []
    made = built.post("/api/sets", json=GENERATE)
    assert made.status_code == 200 and made.json().keys() == {"set_id", "built", "failed", "warnings", "kinds"} and made.json()["built"] == 2
    set_id = made.json()["set_id"]
    index = built.get("/api/sets").json()
    assert [row["set_id"] for row in index] == [set_id] and (index[0]["n_blocks"], index[0]["n_guesses"]) == (2, 0)
    header = built.get(f"/api/sets/{set_id}")
    assert header.status_code == 200 and {"recipe_real", "recipe_synthetic", "camera", "blocks"} <= header.json().keys() and len(header.json()["blocks"]) == 2
    assert built.get("/api/health").json()["synthetic"]["counts"] == {"sets": 1, "blocks": 2, "guesses": 0}
    ready = built.get("/api/blocks", params={"which": f"set:{set_id}", **SHORT})
    assert ready.status_code == 200 and ready.json()["totals"]["blocks"] == 2 and list(ready.json()["built"]) == [set_id]
    block_id = ready.json()["blocks"][0]["block_id"]
    assert built.get(f"/api/blocks/{block_id}").status_code == 200 and built.get(f"/api/blocks/{block_id}/arrays").status_code == 200
    assert built.get(f"/api/blocks/{block_id}/windows", params=SHORT).json()["count"] == ready.json()["blocks"][0]["count"]
    opened = built.post(f"/api/sets/{set_id}/pairs", json={"kind": "track"})
    assert opened.status_code == 200 and opened.json().keys() == {"pair_id", "kind", "sides"} and opened.json()["kind"] == "track"
    pair_id = opened.json()["pair_id"]
    for side in SIDES:
        header = built.get(f"/api/pairs/{pair_id}/{side}")
        assert header.status_code == 200 and header.json().keys() == HEADER_KEYS and header.json()["row"].keys() == set(QUIZ_ROW_KEYS)
        arrays = built.get(f"/api/pairs/{pair_id}/{side}/arrays")
        assert arrays.status_code == 200 and arrays.headers["content-type"] == MEDIA_TYPE
        assert table_of(arrays).schema.names == list(QUIZ_COLUMNS) and table_of(arrays).num_rows == header.json()["row"]["n_frames"]
    guessed = built.post(f"/api/sets/{set_id}/guesses", json={"pair_id": pair_id, "side": "left"})
    assert guessed.status_code == 200 and guessed.json().keys() == {"correct", "real_side", "real_block", "synthetic_block", "tally"}
    assert guessed.json()["correct"] == (guessed.json()["real_side"] == "left") and guessed.json()["tally"]["n"] == 1
    guesses = built.get(f"/api/sets/{set_id}/guesses")
    assert guesses.status_code == 200 and guesses.json()["tally"] == guessed.json()["tally"] and len(guesses.json()["guesses"]) == 1
    assert built.get(f"/api/pairs/{pair_id}/left").status_code == 404
    any_kind = built.post(f"/api/sets/{set_id}/pairs", json={"kind": None})
    assert any_kind.status_code == 200 and any_kind.json()["kind"] in ("arena", "track")
    deleted = built.delete(f"/api/sets/{set_id}")
    assert deleted.status_code == 200 and deleted.json() == {"deleted": True, "blocks": 2}
    assert built.get("/api/sets").json() == [] and not (synthetic / "sets" / set_id).exists()
    assert built.get(f"/api/sets/{set_id}").status_code == 404 and built.get(f"/api/pairs/{any_kind.json()['pair_id']}/left").status_code == 404


def test_the_refusals_of_the_synthetic_routes(built):
    assert built.get("/api/pairs/nope/left").status_code == 404 and built.get("/api/pairs/nope/left/arrays").status_code == 404
    assert built.get("/api/pairs/nope/middle").status_code == 422
    refused = built.post("/api/sets", json={**GENERATE, "sources": [S1, S2]})
    assert refused.status_code == 400 and refused.json() == {"error": f"session {S2} has no built blocks"}
    assert built.post("/api/sets", json={**GENERATE, "length_s": {"maze": 10}}).status_code == 422
    assert built.post("/api/sets", json={**GENERATE, "seed": 1.5}).status_code == 422
    assert built.post("/api/sets", json={**GENERATE, "bogus": 1}).status_code == 422
    assert built.post("/api/sets/nope/pairs", json={"kind": None}).status_code == 404
    assert built.post("/api/sets/nope/guesses", json={"pair_id": "x", "side": "up"}).status_code == 422
    assert built.post("/api/sets/nope/guesses", json={"pair_id": "x", "side": "left"}).status_code == 404
    assert built.get("/api/sets/nope/guesses").status_code == 404
    assert built.get("/api/blocks", params={"which": "set:nope", **SHORT}).status_code == 404
    assert built.get("/api/blocks", params={"which": "nope", **SHORT}).status_code == 400
    assert built.get("/api/sets").json() == []
