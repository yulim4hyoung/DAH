"""B3 — CAN 침입탐지 MLP (통합본 Part 6, "Securing the CAN bus using DL" 계열).

윈도 특징(F=8) → 4클래스(정상/DoS/퍼지/스푸핑). 경량 MLP.
"""
from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn

from ..sim.can_loader import F


class CanMLP(nn.Module):
    def __init__(self, in_dim: int = F, hidden: int = 64, n_classes: int = 4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, n_classes))

    def forward(self, x):
        return self.net(x)


def fit_scaler(X):
    return {"mean": X.mean(0).astype(np.float32), "std": (X.std(0) + 1e-6).astype(np.float32)}


def apply_scaler(X, s):
    return (X - s["mean"]) / s["std"]


def train_model(Xtr, ytr, Xval, yval, cfg):
    hp = cfg["can"]["mlp"]
    scaler = fit_scaler(Xtr)
    xt = torch.tensor(apply_scaler(Xtr, scaler)); yt = torch.tensor(ytr)
    xv = torch.tensor(apply_scaler(Xval, scaler)); yv = torch.tensor(yval)
    model = CanMLP(hidden=hp["hidden"])
    opt = torch.optim.Adam(model.parameters(), lr=hp["lr"])
    lossf = nn.CrossEntropyLoss()
    n = len(xt); bs = hp["batch"]; history = []
    for ep in range(hp["epochs"]):
        model.train(); perm = torch.randperm(n); tot = 0.0
        for i in range(0, n, bs):
            idx = perm[i:i + bs]
            opt.zero_grad(); out = model(xt[idx]); loss = lossf(out, yt[idx])
            loss.backward(); opt.step(); tot += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            vacc = (model(xv).argmax(1) == yv).float().mean().item()
        history.append({"epoch": ep + 1, "train_loss": tot / n, "val_acc": vacc})
    return model, scaler, history


@torch.no_grad()
def predict(model, scaler, X):
    model.eval()
    xs = torch.tensor(apply_scaler(X.astype(np.float32), scaler))
    logits = model(xs)
    return torch.softmax(logits, 1).numpy()
