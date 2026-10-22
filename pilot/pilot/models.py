"""
The pilot's networks: a recurrent predictor with a step by step trace path, and a memoryless MLP of the same width.
"""

import torch
from torch import nn

# Initialisation is PyTorch's default, left alone. Every nn.RNN and nn.GRU weight and bias is uniform in
# +-1/sqrt(n_hidden); nn.Linear weights and biases are uniform in +-1/sqrt(fan_in) (Kaiming uniform with a = sqrt(5)).
# The initial hidden state is zero. The draws come from the global torch generator, so the caller seeds it with
# torch.manual_seed before building a model. At this scale an untrained net stays near the linear range of tanh, and
# trained seed s starts from the weights of untrained seed s (pilot.md Appendix C, issue 36: open for the authors).


class PredictiveRNN(nn.Module):
    """
    A tanh RNN (or the GRU fallback) from the inputs to a hidden state, and a linear readout to the place target.
    """

    def __init__(self, n_in, n_hidden, n_out, rnn_type="vanilla", freeze_recurrent=False):
        super().__init__()
        self.rnn_type = rnn_type
        if rnn_type == "vanilla":
            self.rnn = nn.RNN(n_in, n_hidden, nonlinearity="tanh", batch_first=True)
        else:
            self.rnn = nn.GRU(n_in, n_hidden, batch_first=True)
        self.readout = nn.Linear(n_hidden, n_out)
        if freeze_recurrent:  # the untrained kind: input and recurrent weights stay at their random draw
            for parameter in self.rnn.parameters():
                parameter.requires_grad = False

    # The vanilla network's weights under the brief's names; run_trace reads them, so both paths share one set.
    @property
    def w_in(self):
        return self.rnn.weight_ih_l0

    @property
    def w_rec(self):
        return self.rnn.weight_hh_l0

    @property
    def bias(self):
        return self.rnn.bias_ih_l0 + self.rnn.bias_hh_l0

    def forward(self, x, trace=False):
        """
        Run x (B, T, n_in) from a zero hidden state; return (prediction, hidden), plus the trace dict if trace.
        """
        if trace and self.rnn_type == "vanilla":
            return self.run_trace(x)
        hidden, _ = self.rnn(x)
        prediction = self.readout(hidden)
        if trace:  # the GRU has no single w_in and w_rec to split, so its trace holds only hidden and prediction
            return prediction, hidden, {"hidden": hidden, "prediction": prediction}
        return prediction, hidden

    def run_trace(self, x):
        """
        The step by step path over the nn.RNN weights: one matmul for the input drive, a loop for the recurrent drive.
        """
        input_drive = x @ self.w_in.T
        h = x.new_zeros(x.shape[0], self.w_rec.shape[0])
        recurrent_drive, pre_activation, hidden = [], [], []
        for t in range(x.shape[1]):
            recurrent_drive.append(h @ self.w_rec.T)
            pre_activation.append(input_drive[:, t] + recurrent_drive[-1] + self.bias)
            h = torch.tanh(pre_activation[-1])
            hidden.append(h)
        recurrent_drive = torch.stack(recurrent_drive, dim=1)
        pre_activation = torch.stack(pre_activation, dim=1)
        hidden = torch.stack(hidden, dim=1)
        prediction = self.readout(hidden)
        trace = {
            "input_drive": input_drive,
            "recurrent_drive": recurrent_drive,
            "pre_activation": pre_activation,
            "hidden": hidden,
            "prediction": prediction,
        }
        return prediction, hidden, trace


class MemorylessMLP(nn.Module):
    """
    One tanh hidden layer applied to each step on its own, so it sees the current step and nothing before it.
    """

    def __init__(self, n_in, n_hidden, n_out):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, n_hidden), nn.Tanh(), nn.Linear(n_hidden, n_out))

    def forward(self, x):
        """
        Map x (B, T, n_in) to the prediction (B, T, n_out), step by step.
        """
        return self.net(x)
