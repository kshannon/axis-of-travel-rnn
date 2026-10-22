"""
The networks: a vanilla tanh RNN predictor with a step by step trace path, and a memoryless MLP of the same width.
"""

import torch
from torch import nn

# Initialisation is PyTorch's default, left alone. Every nn.RNN weight and bias is uniform in +-1/sqrt(hidden_size),
# nn.Linear weights and biases uniform in +-1/sqrt(fan_in). The initial hidden state is zero. train.make_model draws the
# weights from a seeded generator forked off the global one, so a seed fixes them and the global state is left as it was.
KINDS = ("rnn", "memoryless")


class PredictiveRNN(nn.Module):
    """
    A tanh RNN from the inputs to a hidden state, and a linear readout to the future position.
    """

    def __init__(self, n_in, hidden_size, n_out):
        super().__init__()
        self.rnn = nn.RNN(n_in, hidden_size, nonlinearity="tanh", batch_first=True)
        self.readout = nn.Linear(hidden_size, n_out)

    # The weights under the brief's names; run_trace reads them, so both paths share one set.
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
        Run x (B, T, n_in) from a zero hidden state and return (prediction, hidden), plus the trace dict if trace.
        """
        if trace:
            return self.run_trace(x)
        hidden, _ = self.rnn(x)
        return self.readout(hidden), hidden

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
        hidden = torch.stack(hidden, dim=1)
        prediction = self.readout(hidden)
        trace = {"input_drive": input_drive, "recurrent_drive": torch.stack(recurrent_drive, dim=1),
                 "pre_activation": torch.stack(pre_activation, dim=1), "hidden": hidden, "prediction": prediction}
        return prediction, hidden, trace


class MemorylessMLP(nn.Module):
    """
    One tanh hidden layer applied to each step on its own, so it sees the current step and nothing before it.
    """

    def __init__(self, n_in, hidden_size, n_out):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, hidden_size), nn.Tanh(), nn.Linear(hidden_size, n_out))

    def forward(self, x):
        """
        Map x (B, T, n_in) to the prediction (B, T, n_out), step by step.
        """
        return self.net(x)
