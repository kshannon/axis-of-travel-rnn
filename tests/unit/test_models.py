"""
The networks: output shapes, the trace path agreeing with the fast path over the whole window, and seeded weights.
"""

import torch

from axis_of_travel_rnn.train import make_model

BATCH, STEPS, N_IN, HIDDEN, N_OUT = 3, 17, 2, 8, 2


def test_shapes_and_the_hidden_trace_cover_every_step():
    rnn = make_model("rnn", N_IN, N_OUT, HIDDEN, seed=0)
    x = torch.randn(BATCH, STEPS, N_IN, generator=torch.Generator().manual_seed(0))
    prediction, hidden = rnn(x)
    assert prediction.shape == (BATCH, STEPS, N_OUT) and hidden.shape == (BATCH, STEPS, HIDDEN)
    _, traced, trace = rnn(x, trace=True)
    assert trace["hidden"].shape[1] == STEPS and trace["recurrent_drive"].shape == (BATCH, STEPS, HIDDEN)
    assert torch.allclose(traced, hidden, atol=1e-5)
    assert make_model("memoryless", N_IN, N_OUT, HIDDEN, seed=0)(x).shape == (BATCH, STEPS, N_OUT)


def test_a_seed_fixes_the_weights_and_leaves_the_global_generator_alone():
    state = torch.random.get_rng_state()
    a, b = make_model("rnn", N_IN, N_OUT, HIDDEN, seed=5), make_model("rnn", N_IN, N_OUT, HIDDEN, seed=5)
    assert all(torch.equal(p, q) for p, q in zip(a.parameters(), b.parameters()))
    assert torch.equal(state, torch.random.get_rng_state())
