"""
The pilot's networks: shapes, trace and fast paths agree, the trace adds up, frozen weights stay, the MLP has no memory.
"""

import pytest
import torch

from pilot.models import MemorylessMLP, PredictiveRNN

N_HIDDEN, N_OUT = 128, 100
N_IN = {"place_only": 100, "place_motion": 102, "full": 132}
B, T = 3, 40


def make_input(n_in):
    return torch.randn(B, T, n_in, generator=torch.Generator().manual_seed(0))


def make_model(n_in=100, **kwargs):
    torch.manual_seed(0)
    return PredictiveRNN(n_in, N_HIDDEN, N_OUT, **kwargs)


@pytest.mark.parametrize("input_set", N_IN)
def test_output_shapes_for_each_input_set(input_set):
    x = make_input(N_IN[input_set])
    prediction, hidden = make_model(N_IN[input_set])(x)
    assert prediction.shape == (B, T, N_OUT) and hidden.shape == (B, T, N_HIDDEN)
    assert MemorylessMLP(N_IN[input_set], N_HIDDEN, N_OUT)(x).shape == (B, T, N_OUT)
    prediction, hidden, trace = make_model(N_IN[input_set], rnn_type="gru")(x, trace=True)
    assert prediction.shape == (B, T, N_OUT) and hidden.shape == (B, T, N_HIDDEN)
    assert set(trace) == {"hidden", "prediction"}


def test_trace_and_fast_paths_agree():
    x = make_input(100)
    model = make_model()
    prediction, hidden = model(x)
    trace_prediction, trace_hidden, trace = model(x, trace=True)
    assert torch.allclose(trace_hidden, hidden, atol=1e-5)
    assert torch.allclose(trace_prediction, prediction, atol=1e-5)
    assert trace["hidden"] is trace_hidden and trace["prediction"] is trace_prediction
    for name in ("input_drive", "recurrent_drive", "pre_activation", "hidden"):
        assert trace[name].shape == (B, T, N_HIDDEN)


def test_trace_adds_up_and_starts_from_zero():
    x = make_input(100)
    model = make_model()
    _, _, trace = model(x, trace=True)
    summed = trace["input_drive"] + trace["recurrent_drive"] + model.rnn.bias_ih_l0 + model.rnn.bias_hh_l0
    assert torch.allclose(trace["pre_activation"], summed, atol=1e-6)
    assert torch.allclose(trace["hidden"], torch.tanh(trace["pre_activation"]), atol=1e-6)
    assert (trace["recurrent_drive"][:, 0] == 0).all()
    assert (trace["recurrent_drive"][:, 1] != 0).any()


def test_frozen_recurrent_weights_stay_while_the_readout_trains():
    x = make_input(100)
    model = make_model(freeze_recurrent=True)
    rnn_before = [p.detach().clone() for p in model.rnn.parameters()]
    readout_before = [p.detach().clone() for p in model.readout.parameters()]
    optimiser = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss = (model(x)[0] - torch.randn(B, T, N_OUT, generator=torch.Generator().manual_seed(1))).pow(2).mean()
    loss.backward()
    optimiser.step()
    assert all(torch.equal(p, q) for p, q in zip(model.rnn.parameters(), rnn_before))
    assert not any(torch.equal(p, q) for p, q in zip(model.readout.parameters(), readout_before))


def test_memoryless_sees_only_the_current_step():
    x = make_input(100)
    changed = x.clone()
    changed[:, :-1] += 1.0
    mlp = MemorylessMLP(100, N_HIDDEN, N_OUT)
    assert torch.equal(mlp(x)[:, -1], mlp(changed)[:, -1])
    rnn = make_model()
    assert not torch.allclose(rnn(x)[0][:, -1], rnn(changed)[0][:, -1])
