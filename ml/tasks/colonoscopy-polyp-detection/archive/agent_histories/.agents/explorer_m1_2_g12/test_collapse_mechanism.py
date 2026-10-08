import torch
import torch.nn as nn
import numpy as np

# Test 1: Standard nn.Dropout2d when model.eval() is called and only a boolean flag is set
class DummyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.mc_dropout = False
        self.drop = nn.Dropout2d(p=0.2)
        self.conv = nn.Conv2d(3, 16, 3, padding=1)

    def enable_mc_dropout(self):
        self.mc_dropout = True

    def forward(self, x):
        feat = self.conv(x)
        if self.mc_dropout or self.training:
            feat = self.drop(feat)
        return feat

m = DummyModel()
m.eval()
m.enable_mc_dropout()

x = torch.randn(1, 3, 32, 32)
passes = []
for _ in range(16):
    passes.append(m(x).detach().numpy())

passes = np.stack(passes, axis=0)
var = np.var(passes, axis=0)
print("DummyModel var mean:", np.mean(var))
print("DummyModel var max:", np.max(var))
print("Variance collapsed?", np.max(var) == 0.0)
