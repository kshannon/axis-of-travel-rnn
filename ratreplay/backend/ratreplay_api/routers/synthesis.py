"""
The HTTP face of SynthesisManager: the synthetic sets, generating and deleting one, and the quiz, a pair opened over a set, its two sides without their names, and the guesses.
"""

from fastapi import APIRouter, Depends

from ..schemas import GenerateBody, GuessBody, PairBody, Side
from ..utilities import arrow
from .deps import synthesis_manager

router = APIRouter(prefix="/api")


@router.get("/sets")
def set_index(manager=Depends(synthesis_manager)):
    """
    One row per synthetic set with when and by whom it was made, its sources, seed, lengths, block counts and kinds, and how the guesses against it stand.
    """
    return manager.index()


@router.post("/sets")
def generate_set(body: GenerateBody, manager=Depends(synthesis_manager)):
    """
    Generate a set from the built blocks of the source sessions with the seed and the lengths per kind, returning its id, how many blocks were built, which failed, the warnings and the kinds.
    """
    return manager.generate(body.sources, body.seed, body.length_s, body.settings.model_dump())


@router.get("/sets/{set_id}")
def set_header(set_id: str, manager=Depends(synthesis_manager)):
    """
    A set's provenance, both recipes among it, with the rows of its blocks.
    """
    return manager.set(set_id)


@router.delete("/sets/{set_id}")
def delete_set(set_id: str, manager=Depends(synthesis_manager)):
    """
    Remove the set whole, returning whether there was one and how many blocks went.
    """
    return manager.delete_set(set_id)


@router.post("/sets/{set_id}/pairs")
def open_pair(set_id: str, body: PairBody, manager=Depends(synthesis_manager)):
    """
    Open a quiz pair over the set, of the body's kind or any the set has, returning its id, the kind and the two sides.
    """
    return manager.pair(set_id, body.kind)


@router.get("/pairs/{pair_id}/{side}")
def pair_block(pair_id: str, side: Side, manager=Depends(synthesis_manager)):
    """
    The block on one side of an open pair as a player header, nothing in it naming its source.
    """
    return manager.pair_block(pair_id, side)


@router.get("/pairs/{pair_id}/{side}/arrays", response_class=arrow.ArrowResponse)
def pair_arrays(pair_id: str, side: Side, manager=Depends(synthesis_manager)):
    """
    The arrays of the block on one side of an open pair, without its labels, as an Arrow IPC stream.
    """
    return arrow.ArrowResponse(arrow.encode(manager.pair_arrays(pair_id, side)))


@router.post("/sets/{set_id}/guesses")
def record_guess(set_id: str, body: GuessBody, manager=Depends(synthesis_manager)):
    """
    Record which side of the pair the person called real, close the pair and reveal it with the set's tally.
    """
    return manager.guess(set_id, body.pair_id, body.side)


@router.get("/sets/{set_id}/guesses")
def set_guesses(set_id: str, manager=Depends(synthesis_manager)):
    """
    The set's tally and every guess made against it.
    """
    return manager.guesses(set_id)
