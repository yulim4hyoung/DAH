"""A2 — GNSS 스푸핑/재밍 탐지용 1D-CNN (통합본 Part 6, Sun[43]·Sung[45] 계열).

입력: (batch, F=7, window) 다특징 시계열 → 3클래스(정상/스푸핑/재밍).
채널 표준화 통계를 모델과 함께 저장해 추론 시 동일 적용.
"""
from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn

from ..sim.gnss_sim import F, make_windows


class GnssCNN(nn.Module):
    def __init__(self, in_ch: int = F, ch: int = 32, n_classes: int = 3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(in_ch, ch, kernel_size=5, padding=2), nn.ReLU(),
            nn.Conv1d(ch, ch, kernel_size=3, padding=1), nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(ch, ch), nn.ReLU(),
                                  nn.Dropout(0.2), nn.Linear(ch, n_classes))

    def forward(self, x):
        return self.head(self.net(x))


def fit_scaler(X: np.ndarray) -> dict:
    """채널(특징)별 평균·표준편차. X:(N,F,W)."""
    mean = X.mean(axis=(0, 2))
    std = X.std(axis=(0, 2)) + 1e-6
    return {"mean": mean.astype(np.float32), "std": std.astype(np.float32)}


def apply_scaler(X: np.ndarray, scaler: dict) -> np.ndarray:
    m = scaler["mean"][None, :, None]
    s = scaler["std"][None, :, None]
    return (X - m) / s


def train_model(Xtr, ytr, Xval, yval, cfg: dict):
    hp = cfg["gnss"]["cnn"]
    scaler = fit_scaler(Xtr)
    Xtr_s = apply_scaler(Xtr, scaler)
    Xval_s = apply_scaler(Xval, scaler)
    model = GnssCNN(ch=hp["channels"])
    opt = torch.optim.Adam(model.parameters(), lr=hp["lr"])
    lossf = nn.CrossEntropyLoss()

    xt = torch.tensor(Xtr_s); yt = torch.tensor(ytr)
    xv = torch.tensor(Xval_s); yv = torch.tensor(yval)
    n = len(xt); bs = hp["batch"]
    history = []
    for ep in range(hp["epochs"]):
        model.train()
        perm = torch.randperm(n)
        tot = 0.0
        for i in range(0, n, bs):
            idx = perm[i:i + bs]
            opt.zero_grad()
            out = model(xt[idx])
            loss = lossf(out, yt[idx])
            loss.backward(); opt.step()
            tot += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            vacc = (model(xv).argmax(1) == yv).float().mean().item()
        history.append({"epoch": ep + 1, "train_loss": tot / n, "val_acc": vacc})
    return model, scaler, history


@torch.no_grad()
def predict_proba(model, scaler, X: np.ndarray) -> np.ndarray:
    model.eval()
    xs = apply_scaler(X.astype(np.float32), scaler)
    logits = model(torch.tensor(xs))
    return torch.softmax(logits, dim=1).numpy()


@torch.no_grad()
def score_flight(model, scaler, feat: np.ndarray, window: int):
    """비행 시퀀스를 슬라이딩하며 에폭별 (예측클래스, 공격확률) 산출 → 탐지지연 측정용.
    반환: epochs_idx(list), pred(list), attack_prob(list) — 윈도 끝 에폭 기준.
    """
    labels_dummy = np.zeros(len(feat), dtype=int)
    xw, _ = make_windows(feat, labels_dummy, window, stride=1)
    X = np.stack(xw).astype(np.float32)
    probs = predict_proba(model, scaler, X)
    pred = probs.argmax(1)
    attack_prob = 1.0 - probs[:, 0]  # 1 - P(정상)
    idx = list(range(window - 1, len(feat)))
    return idx, pred.tolist(), attack_prob.tolist()
