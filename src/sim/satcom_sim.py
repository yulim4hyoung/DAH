"""B2 — SATCOM 지상관리망(NOC) 이상 트래픽 합성 시뮬레이터 (계층 ⑤).

통합본 2-A·B2 근거. Viasat KA-SAT 2022(AcidRain) 패턴을 재현한다:
  오설정 VPN 진입(인증 이상) → 관리채널로 '정상으로 보이는' 대량 펌웨어 푸시
  → 다수 모뎀 동시 오프라인(와이퍼 효과).
정상 운영만 학습한 오토인코더가 이 이상 버킷을 재구성 오차로 잡아낸다(비지도).

버킷(1분 집계) 특징 F=8:
  [cmd_rate, cmd_type_entropy, fw_push, distinct_modems, auth_fail,
   config_change, modems_offline, offhours]
"""
from __future__ import annotations
import numpy as np

FEATURES = ["cmd_rate", "cmd_type_entropy", "fw_push", "distinct_modems",
            "auth_fail", "config_change", "modems_offline", "offhours"]
F = len(FEATURES)


def _normal_bucket(rng) -> np.ndarray:
    return np.array([
        max(0.0, rng.normal(8.0, 3.0)),   # cmd_rate (명령/분)
        rng.normal(2.0, 0.35),            # 명령유형 엔트로피(다양)
        float(rng.poisson(0.05)),         # 펌웨어 푸시(거의 0, 가끔 예약)
        max(0.0, rng.normal(4.0, 2.0)),   # 대상 모뎀 수(소수 루틴)
        float(rng.poisson(0.3)),          # 인증 실패
        float(rng.poisson(0.8)),          # 설정 변경
        float(rng.poisson(0.1)),          # 모뎀 오프라인
        float(rng.random() < 0.4),        # 야간 플래그
    ], dtype=np.float64)


def generate_window(kind: str, buckets: int, rng):
    """운영 구간(버킷 시퀀스) 생성. 반환 (feat[buckets,F], labels[buckets], onset)."""
    feat = np.zeros((buckets, F))
    labels = np.zeros(buckets, dtype=int)
    onset = -1
    offhours_bias = rng.random() < 0.5
    if kind == "attack":
        onset = int(rng.integers(8, buckets - 12))

    for b in range(buckets):
        x = _normal_bucket(rng)
        if offhours_bias:
            x[7] = float(rng.random() < 0.5)
        if kind == "attack" and b >= onset:
            k = b - onset
            # 1단계(k=0~1): VPN 인증 이상 위주 — 은밀(정상 꼬리와 겹쳐 조기탐지 어려움)
            x[4] += max(0.0, rng.normal(2.5, 1.2)) * np.exp(-k / 5.0)   # auth_fail 완만
            if k >= 1:
                x[0] += rng.normal(5.0, 2.0)               # 명령률 약간 상승
                x[1] -= 0.4                                # 엔트로피 약간 저하
            # 2단계(k>=2): 대량 펌웨어 푸시 + 모뎀 팬아웃 + 저엔트로피(반복)
            if k >= 2:
                push_ramp = min(1.0, (k - 1) / 3.0)
                x[0] += rng.normal(12.0, 4.0)              # 명령률 급증
                x[1] = x[1] * 0.4 - 0.7                    # 엔트로피 저하(반복 푸시)
                x[2] += rng.normal(6.0, 2.0) * push_ramp   # 펌웨어 푸시 버스트
                x[3] += rng.normal(80.0, 20.0) * push_ramp  # 모뎀 대량 팬아웃
                x[5] += rng.normal(4.0, 1.0)               # 설정 변경 증가
            # 3단계(k>=3): 와이퍼 효과 → 모뎀 동시 오프라인 누적
            if k >= 3:
                x[6] += max(0.0, rng.normal(min((k - 2) * 4.0, 45.0), 5.0))
            x[7] = 1.0 if rng.random() < 0.7 else x[7]      # 야간 편향
            labels[b] = 1
        feat[b] = x

    feat[:, 1] = np.clip(feat[:, 1], 0.0, 3.5)   # 엔트로피
    feat = np.clip(feat, 0.0, None)
    return feat.astype(np.float32), labels, onset


def generate_dataset(cfg: dict, rng):
    """반환:
      Xtrain_normal (정상 버킷, AE 학습),
      Xtest (버킷), ytest (0/1),
      attack_windows (list of (feat, labels, onset)) — 탐지지연·예시용,
      meta
    """
    buckets = cfg["satcom"]["bucket_len"]
    n_norm = cfg["satcom"]["n_normal"]
    n_atk = cfg["satcom"]["n_attack"]

    normal_windows = [generate_window("normal", buckets, rng) for _ in range(n_norm)]
    attack_windows = [generate_window("attack", buckets, rng) for _ in range(n_atk)]

    # 정상 윈도 80/20 → 학습/시험
    n_tr = int(0.8 * n_norm)
    train_norm = normal_windows[:n_tr]
    test_norm = normal_windows[n_tr:]

    Xtrain = np.concatenate([w[0] for w in train_norm], axis=0)
    # 시험셋 = 남은 정상 버킷 + 공격 버킷
    Xtest_parts, ytest_parts = [], []
    for feat, labels, _ in test_norm:
        Xtest_parts.append(feat); ytest_parts.append(labels)
    for feat, labels, _ in attack_windows:
        Xtest_parts.append(feat); ytest_parts.append(labels)
    Xtest = np.concatenate(Xtest_parts, axis=0)
    ytest = np.concatenate(ytest_parts, axis=0)

    meta = {"n_normal": n_norm, "n_attack": n_atk, "buckets_per_window": buckets,
            "n_train_normal_buckets": int(len(Xtrain)),
            "n_test_buckets": int(len(Xtest)),
            "test_attack_ratio": float(ytest.mean()),
            "features": FEATURES}
    return Xtrain, Xtest, ytest, attack_windows, meta
