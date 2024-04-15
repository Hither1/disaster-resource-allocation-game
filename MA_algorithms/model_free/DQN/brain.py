import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

HUBER_LOSS_DELTA = 1.0


def huber_loss(y_true, y_predict):
    err = y_true - y_predict

    cond = torch.abs(err) < HUBER_LOSS_DELTA
    L2 = 0.5 * err**2
    L1 = HUBER_LOSS_DELTA * (torch.abs(err) - 0.5 * HUBER_LOSS_DELTA)
    loss = torch.where(cond, L2, L1)

    return torch.mean(loss)


class Brain(nn.Module):
    def __init__(self, state_size, action_size, brain_name, arguments):
        super(Brain, self).__init__()
        self.state_size = state_size
        self.action_size = action_size
        self.weight_backup = brain_name
        self.batch_size = arguments['batch_size']
        self.learning_rate = arguments['learning_rate']
        self.test = arguments['test']
        self.num_nodes = arguments['number_nodes']
        self.dueling = arguments['dueling']
        self.optimizer_model = arguments['optimizer']
        self.model = self._build_model()
        self.model_ = self._build_model()

    def _build_model(self):
        if self.dueling:
            layers = []
            layers += [nn.Linear(self.state_size, self.num_nodes), nn.ReLU()]
            layers += [nn.Linear(self.num_nodes, self.num_nodes), nn.ReLU()]
            value_stream = nn.Sequential(*layers)
            advantage_stream = nn.Sequential(*layers)

            value = nn.Linear(self.num_nodes, 1)
            advantage = nn.Linear(self.num_nodes, self.action_size)

            return nn.Sequential(value_stream, value), nn.Sequential(advantage_stream, advantage)
        else:
            layers = []
            layers += [nn.Linear(self.state_size, self.num_nodes), nn.ReLU()]
            layers += [nn.Linear(self.num_nodes, self.num_nodes), nn.ReLU()]
            layers += [nn.Linear(self.num_nodes, self.action_size)]
            return nn.Sequential(*layers)

    def forward(self, x):
        if self.dueling:
            value, advantage = self.model[0](x), self.model[1](x)
            Q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
            return Q_values
        else:
            return self.model(x)

    def train(self, x, y, sample_weight=None, epochs=1, verbose=False):
        criterion = huber_loss
        optimizer = getattr(optim, self.optimizer_model)(self.model.parameters(), lr=self.learning_rate)

        inputs = torch.tensor(x, dtype=torch.float32)
        targets = torch.tensor(y, dtype=torch.float32)

        for _ in range(epochs):
            optimizer.zero_grad()
            outputs = self(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

    def predict(self, state, target=False):
        with torch.no_grad():
            state = torch.tensor(state, dtype=torch.float32)
            if target:
                return self.model_(state).numpy()
            else:
                return self.model(state).numpy()

    def predict_one_sample(self, state, target=False):
        return self.predict(np.expand_dims(state, axis=0), target=target).flatten()

    def update_target_model(self):
        self.model_.load_state_dict(self.model.state_dict())

    def save_model(self):
        torch.save(self.state_dict(), self.weight_backup)
