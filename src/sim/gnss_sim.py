"""A2 — GNSS 스푸핑/재밍 합성 시뮬레이터 (계층 ⑦).

통합본 2-B·A2-2 근거로 GNSS 수신기 관측치(에폭 1Hz)를 생성한다.
민간 L1 C/A는 무인증·초저전력이라, 스푸핑은 '급변'이 아니라 *점진 표류*로
INS 잔차를 서서히 키우는 게 정석(흑해·민항 IRS 오염 패턴). 재밍은 C/N0를 붕괴시킨다.

특징(F=7): [cn0_mean, cn0_std, agc, ins_residual, dop, clock_jump, num_sats]
  - cn0_mean : 반송파대잡음비 평균(dB-Hz). 스푸퍼는 강·균일 → 상승+std 저하
  - cn0_std  : 위성 간 C/N0 산포. 스푸핑은 비정상적으로 낮음(균일)
  - agc      : 자동이득제어(정규화 0~1). 강한 입력=스푸핑 시 하강, 재밍 시 포화
  - ins_residual : GNSS-INS 위치 잔차(m). 스푸핑의 핵심 신호 = 점진 확대
  - dop      : 정밀도저하율. 스푸핑은 의심스럽게 낮음, 재밍은 상승
  - clock_jump : 수신기 클럭 바이어스 변화(ns)
  - num_sats : 추적 위성 수. 재밍 시 급감

라벨: 0=정상, 1=스푸핑, 2=재밍
"""
from __future__ import annotations
import numpy as np

FEATURES = ["cn0_mean", "cn0_std", "agc", "ins_residual", "dop", "clock_jump", "num_sats"]
F = len(FEATURES)
CLASS_NAMES = ["정상", "스푸핑", "재밍"]
KINDS = ["nominal", "spoof", "jam"]


def _nominal_epoch(rng) -> np.ndarray:
    return np.array([
        rng.normal(44.0, 1.8),      # cn0_mean
        rng.normal(3.0, 0.7),       # cn0_std
        rng.normal(0.50, 0.035),    # agc
        abs(rng.normal(2.2, 0.8)),  # ins_residual
        rng.normal(2.1, 0.5),       # dop
        rng.normal(0.0, 1.2),       # clock_jump
        rng.normal(11.0, 0.9),      # num_sats
    ], dtype=np.float64)


def generate_flight(kind: str, epochs: int, rng, window: int = 20):
    """한 비행(에폭 시퀀스) 생성. 반환: (feat[epochs,F], labels[epochs], onset)."""
    feat = np.zeros((epochs, F))
    labels = np.zeros(epochs, dtype=int)
    onset = -1
    if kind != "nominal":
        onset = int(rng.integers(window + 8, epochs - window - 4))

    for t in range(epochs):
        x = _nominal_epoch(rng)
        if kind != "nominal" and t >= onset:
            k = t - onset  # 공격 경과(초)
            if kind == "spoof":
                # 은밀한 점진 표류: 개시 직후엔 정상과 거의 구분 안 됨(탐지 회피).
                # ramp로 서서히 정체가 드러나고 잔차가 확대 → 유의미한 탐지지연 발생.
                ramp = min(1.0, k / 25.0)             # ~25초에 걸쳐 완전 발현
                slope = 0.45                          # m/s 표류율
                x[0] += ramp * rng.normal(3.5, 1.2)   # C/N0 서서히 상승
                x[1] = x[1] * (1 - ramp) + ramp * rng.normal(1.2, 0.35)  # 산포 서서히 균일화
                x[2] -= ramp * rng.normal(0.13, 0.03)  # AGC 서서히 하강
                x[3] = 2.2 + slope * k + rng.normal(0, 1.0)   # 잔차 점진 확대
                x[4] = x[4] * (1 - ramp) + ramp * rng.normal(1.4, 0.2)   # DOP 서서히 낮아짐
                x[5] = rng.normal(1.2, 1.1) + 0.04 * k  # 클럭 바이어스 드리프트
                x[6] = rng.normal(11.3, 0.8)           # 위성 수 유지(스푸퍼 제공)
                labels[t] = 1
            elif kind == "jam":
                # 재밍: C/N0 붕괴·위성 손실·AGC 포화. 가용성 공격이라 탐지는 비교적 빠름.
                sev = min(1.0, 0.15 + 0.06 * k)
                x[0] -= sev * rng.normal(15.0, 2.5)    # C/N0 붕괴
                x[1] += sev * rng.normal(3.0, 1.0)     # 산포 상승(불안정)
                x[2] = min(0.99, x[2] + sev * rng.normal(0.4, 0.08))  # AGC 포화
                x[3] = 2.2 + sev * 1.2 * k + rng.normal(0, 1.4)  # 잔차 급확대
                x[4] += sev * rng.normal(3.0, 1.0)     # DOP 상승
                x[5] = rng.normal(0.0, 6.0)            # 클럭 요동
                x[6] -= sev * rng.normal(6.0, 1.2)     # 위성 급감
                labels[t] = 2
        feat[t] = x

    # 물리적 범위 클리핑
    feat[:, 0] = np.clip(feat[:, 0], 8, 54)     # cn0
    feat[:, 1] = np.clip(feat[:, 1], 0.3, 9)
    feat[:, 2] = np.clip(feat[:, 2], 0.05, 1.0)  # agc
    feat[:, 3] = np.clip(feat[:, 3], 0.1, 200)   # residual
    feat[:, 4] = np.clip(feat[:, 4], 0.8, 12)    # dop
    feat[:, 6] = np.clip(np.round(feat[:, 6]), 3, 14)  # num_sats
    return feat.astype(np.float32), labels, onset


def make_windows(feat, labels, window: int, stride: int = 2):
    """에폭 t에서 끝나는 길이 window 윈도 → (X[F,window], y=label[t])."""
    Xs, ys = [], []
    for t in range(window - 1, len(feat), stride):
        Xs.append(feat[t - window + 1:t + 1].T)  # (F, window)
        ys.append(int(labels[t]))
    return Xs, ys


def generate_dataset(cfg: dict, rng):
    """학습용 데이터셋 생성. 반환: X(N,F,W) float32, y(N,), meta."""
    epochs = cfg["gnss"]["epochs"]
    window = cfg["gnss"]["window"]
    n = cfg["gnss"]["n_flights"]
    Xs, ys = [], []
    counts = {"nominal": 0, "spoof": 0, "jam": 0}
    for _ in range(n):
        kind = KINDS[rng.integers(0, 3)]
        counts[kind] += 1
        feat, labels, _ = generate_flight(kind, epochs, rng, window)
        xw, yw = make_windows(feat, labels, window)
        Xs.extend(xw)
        ys.extend(yw)
    X = np.stack(Xs).astype(np.float32)  # (N, F, W)
    y = np.array(ys, dtype=np.int64)
    meta = {"n_flights": n, "epochs": epochs, "window": window,
            "flight_kinds": counts, "n_windows": int(len(y)),
            "features": FEATURES, "classes": CLASS_NAMES}
    return X, y, meta
