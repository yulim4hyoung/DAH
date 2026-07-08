"""B3 — CAN 버스 침입탐지 데이터 (계층 ⑧).

실 공개 데이터셋(Car-Hacking, HCRL) CSV가 data/can/ 에 있으면 로드하고,
없으면 동형(同型) 합성 CAN 스트림을 생성한다(오프라인·재현 가능).

공격 유형(HCRL과 동일 4클래스):
  0 정상 / 1 DoS(0x000 폭주) / 2 퍼지(랜덤 ID·데이터) / 3 스푸핑(정상 ID 위장 주입)

윈도 특징 F=8: [mean_iat, std_iat, min_iat, n_unique_id, max_id_freq,
                id_entropy, known_id_ratio, mean_dlc]
"""
from __future__ import annotations
import os
import glob
import numpy as np

CLASS_NAMES = ["정상", "DoS", "퍼지", "스푸핑"]

# 정상 버스에 상주하는 합법 CAN ID와 주기(ms)
LEGIT_PERIODS = {
    0x130: 10, 0x131: 10, 0x140: 20, 0x153: 20, 0x164: 40,
    0x18F: 50, 0x1F1: 50, 0x220: 100, 0x2A0: 100, 0x2C0: 100,
    0x316: 10, 0x329: 20, 0x370: 200, 0x430: 100, 0x43F: 40, 0x545: 50,
}
LEGIT_IDS = np.array(list(LEGIT_PERIODS.keys()))
SPOOF_TARGET = 0x316   # RPM류 정상 ID 위장
FEATURES = ["mean_iat", "std_iat", "min_iat", "n_unique_id",
            "max_id_freq", "id_entropy", "known_id_ratio", "mean_dlc"]
F = len(FEATURES)


def _normal_messages(t_end: float, rng):
    """정상 버스: 각 합법 ID를 주기+지터로 스케줄."""
    ts, ids, dlc = [], [], []
    for cid, per in LEGIT_PERIODS.items():
        step = per / 1000.0
        t = rng.uniform(0, step)
        while t < t_end:
            ts.append(t); ids.append(cid); dlc.append(8)
            t += step * (1.0 + rng.normal(0, 0.05))
    return np.array(ts), np.array(ids), np.array(dlc)


def _inject(kind: str, t_end: float, rng):
    """공격 메시지(버스트) 생성. 반환 (ts, ids, dlc)."""
    ts, ids, dlc = [], [], []
    # 공격 활성 구간(스트림의 일부에서 버스트)
    n_bursts = rng.integers(3, 6)
    for _ in range(n_bursts):
        b0 = rng.uniform(0, t_end * 0.9)
        b1 = min(t_end, b0 + rng.uniform(0.03, 0.08))
        t = b0
        while t < b1:
            if kind == "dos":
                ids.append(0x000); dlc.append(8); t += 0.0003 * (1 + rng.normal(0, 0.1))
            elif kind == "fuzzy":
                ids.append(int(rng.integers(0, 0x800))); dlc.append(int(rng.integers(0, 9)))
                t += 0.002 * (1 + rng.normal(0, 0.2))
            else:  # spoof
                ids.append(SPOOF_TARGET); dlc.append(8); t += 0.001 * (1 + rng.normal(0, 0.1))
            ts.append(t)
    return np.array(ts), np.array(ids), np.array(dlc)


def _stream(kind: str, t_end: float, rng):
    tn, idn, dn = _normal_messages(t_end, rng)
    atype = np.zeros(len(tn), dtype=int)
    if kind != "normal":
        ta, ida, da = _inject(kind, t_end, rng)
        code = {"dos": 1, "fuzzy": 2, "spoof": 3}[kind]
        tn = np.concatenate([tn, ta]); idn = np.concatenate([idn, ida])
        dn = np.concatenate([dn, da])
        atype = np.concatenate([atype, np.full(len(ta), code)])
    order = np.argsort(tn)
    return tn[order], idn[order], dn[order], atype[order]


def _window_features(t, ids, dlc):
    iat = np.diff(t) * 1000.0 if len(t) > 1 else np.array([0.0])
    iat = np.clip(iat, 0, None)
    uniq, counts = np.unique(ids, return_counts=True)
    p = counts / counts.sum()
    entropy = float(-(p * np.log(p + 1e-12)).sum())
    known = float(np.isin(ids, LEGIT_IDS).mean())
    return np.array([
        float(iat.mean()), float(iat.std()), float(iat.min()),
        float(len(uniq)), float(counts.max() / len(ids)),
        entropy, known, float(np.mean(dlc)),
    ], dtype=np.float32)


def _windows(t, ids, dlc, atype, W, stride, attack_code):
    Xs, ys = [], []
    for i in range(0, len(t) - W, stride):
        sl = slice(i, i + W)
        feats = _window_features(t[sl], ids[sl], dlc[sl])
        frac_atk = float((atype[sl] != 0).mean())
        label = attack_code if frac_atk >= 0.2 else 0
        Xs.append(feats); ys.append(label)
    return Xs, ys


def try_load_real(data_root: str):
    """data/can/*.csv (HCRL Car-Hacking 포맷) 있으면 로드. 없으면 None."""
    files = glob.glob(os.path.join(data_root, "can", "*.csv"))
    if not files:
        return None
    # 포맷: timestamp, can_id(hex), dlc, d0..d(dlc-1), flag('R'정상/'T'주입)
    name_map = {"dos": 1, "fuzzy": 2, "gear": 3, "rpm": 3, "spoof": 3}
    Xs, ys = [], []
    W, stride = 40, 20
    for fp in files:
        code = next((c for k, c in name_map.items() if k in os.path.basename(fp).lower()), 2)
        ts, ids, dlc, atype = [], [], [], []
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 4:
                    continue
                try:
                    ts.append(float(parts[0])); ids.append(int(parts[1], 16))
                    d = int(parts[2]); dlc.append(d)
                    atype.append(1 if parts[-1].upper().startswith("T") else 0)
                except Exception:
                    continue
        if len(ts) < W + 1:
            continue
        ts = np.array(ts); ids = np.array(ids); dlc = np.array(dlc)
        atype = np.array(atype) * code
        xw, yw = _windows(ts, ids, dlc, atype, W, stride, code)
        Xs.extend(xw); ys.extend(yw)
    if not Xs:
        return None
    return np.stack(Xs), np.array(ys, dtype=np.int64), "real(Car-Hacking)"


def generate_windows(cfg: dict, rng, data_root: str | None = None):
    """실데이터 우선, 없으면 합성. 반환 X(N,F), y(N,), source."""
    if cfg["can"].get("use_real_if_present") and data_root:
        real = try_load_real(data_root)
        if real is not None:
            X, y, src = real
            return X, y, src

    W = cfg["can"]["window_msgs"]
    per_class = cfg["can"]["n_windows_per_class"]
    pools = {0: [], 1: [], 2: [], 3: []}
    for kind, code in [("dos", 1), ("fuzzy", 2), ("spoof", 3)]:
        while len(pools[code]) < per_class or len(pools[0]) < per_class:
            t, ids, dlc, atype = _stream(kind, t_end=1.2, rng=rng)
            xw, yw = _windows(t, ids, dlc, atype, W, stride=8, attack_code=code)
            for xf, yf in zip(xw, yw):
                if yf == 0 and len(pools[0]) < per_class:
                    pools[0].append(xf)
                elif yf == code and len(pools[code]) < per_class:
                    pools[code].append(xf)
    Xs, ys = [], []
    for c in range(4):
        for xf in pools[c][:per_class]:
            Xs.append(xf); ys.append(c)
    return np.stack(Xs).astype(np.float32), np.array(ys, dtype=np.int64), "synthetic"
