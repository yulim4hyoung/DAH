"""B2 — SATCOM NOC 관리망 이상탐지용 오토인코더 (통합본 Part 6, Kitsune[50] 계열).

정상 운영 트래픽만 비지도로 학습 → 재구성오차(MSE)가 임계 초과면 이상.
라벨 없이도 신규 공격(AcidRain형 대량 푸시)을 잡는 게 목적.
"""
from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn

from ..sim.satcom_sim import F


class SatcomAE(nn.Module):
    def __init__(self, in_dim: int = F, hidden: int = 32, bottleneck: int = 6):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(),
                                 nn.Linear(hidden, bottleneck), nn.ReLU())
        self.dec = nn.Sequential(nn.Linear(bottleneck, hidden), nn.ReLU(),
                                 nn.Linear(hidden, in_dim))

    def forward(self, x):
        return self.dec(self.enc(x))


def fit_scaler(X: np.ndarray) -> dict:
    return {"mean": X.mean(0).astype(np.float32), "std": (X.std(0) + 1e-6).astype(np.float32)}


def apply_scaler(X, scaler):
    return (X - scaler["mean"]) / scaler["std"]


def recon_error(model, scaler, X: np.ndarray) -> np.ndarray:
    model.eval()
    xs = torch.tensor(apply_scaler(X.astype(np.float32), scaler))
    with torch.no_grad():
        rec = model(xs)
    return ((rec - xs) ** 2).mean(dim=1).numpy()


def train_ae(Xtrain: np.ndarray, cfg: dict):
    hp = cfg["satcom"]["ae"]
    scaler = fit_scaler(Xtrain)
    Xs = torch.tensor(apply_scaler(Xtrain, scaler))
    model = SatcomAE(hidden=hp["hidden"], bottleneck=hp["bottleneck"])
    opt = torch.optim.Adam(model.parameters(), lr=hp["lr"])
    lossf = nn.MSELoss()
    n = len(Xs); bs = hp["batch"]
    history = []
    for ep in range(hp["epochs"]):
        model.train()
        perm = torch.randperm(n); tot = 0.0
        for i in range(0, n, bs):
            idx = perm[i:i + bs]
            opt.zero_grad()
            rec = model(Xs[idx])
            loss = lossf(rec, Xs[idx])
            loss.backward(); opt.step()
            tot += loss.item() * len(idx)
        history.append({"epoch": ep + 1, "train_mse": tot / n})
    # 임계 = 정상 재구성오차의 상위 백분위
    err_tr = recon_error(model, scaler, Xtrain)
    threshold = float(np.percentile(err_tr, hp["threshold_pct"]))
    return model, scaler, threshold, history
