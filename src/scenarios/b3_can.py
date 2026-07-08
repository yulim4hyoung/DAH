"""시나리오 B3 — Wi-Fi→CAN 침투(내부버스 변조). 계층 ④⑧."""
from __future__ import annotations
import os
import numpy as np
import torch

from ..paths import load_config, models_dir
from ..sim.can_loader import _stream, _windows, CLASS_NAMES
from ..detect.can_ids import CanMLP, predict
from ..detect.rules import can_rule

KEY = "b3_can"
TITLE = "Wi-Fi 경유 침투 → CAN 인젝션으로 구동계 변조"
LAYER = "④⑧ 내부버스"
PERSPECTIVE = "한국 군용 UGV(외부 Wi-Fi 진입 → 내부 CAN 표적)"
THREAT = "can_injection"
KILLCHAIN = [
    ("1 스캐닝·정찰", "UGV 주변 Wi-Fi·포트 스캔", "airodump-ng·nmap"),
    ("2 프로토콜분석", "WPA 핸드셰이크·CAN 프레임 구조 분석", "Aircrack-ng·can-utils"),
    ("3 취약점분석", "WPA 약PSK·CAN 무인증 확인", "역분석"),
    ("4 코드생성", "CAN 인젝션 프레임(DoS/퍼지/스푸핑) 제작", "SocketCAN"),
    ("5 침투", "Wi-Fi 침투 후 내부 CAN 버스 접근·주입", "cansend"),
    ("6 무력화", "조향·속도·목적지 변조 → 충돌·탈선", "—"),
]
TARGET = "ROS2/CAN 기반 군용 UGV(정비용 Wi-Fi, 내부 CAN 무인증)"


def load():
    d = torch.load(os.path.join(models_dir(), "b3_can.pt"), weights_only=False)
    m = CanMLP(hidden=d["hp"]["hidden"]); m.load_state_dict(d["state_dict"]); m.eval()
    return {"model": m, "scaler": d["scaler"]}


def attack(rng):
    kind = ["dos", "fuzzy", "spoof"][rng.integers(0, 3)]
    cfg = load_config()
    t, ids, dlc, atype = _stream(kind, t_end=1.2, rng=rng)
    W = cfg["can"]["window_msgs"]
    xw, yw = _windows(t, ids, dlc, atype, W, stride=8, attack_code={"dos": 1, "fuzzy": 2, "spoof": 3}[kind])
    return {"kind": kind, "X": np.stack(xw).astype(np.float32), "y": np.array(yw)}


def detect(bundle, atk):
    X, y = atk["X"], atk["y"]
    probs = predict(bundle["model"], bundle["scaler"], X)
    pred = probs.argmax(1)
    atk_idx = np.where(y != 0)[0]
    hit = atk_idx[pred[atk_idx] != 0] if len(atk_idx) else np.array([], dtype=int)
    detected = len(hit) > 0
    first = int(hit[0]) if detected else (int(atk_idx[0]) if len(atk_idx) else 0)
    sub = int(np.bincount(pred[hit]).argmax()) if detected else 0
    row = X[first]
    _, reasons = can_rule(row)
    evidence = {"미등록ID비율": round(float(1 - row[6]), 2), "단일ID점유": round(float(row[4]), 2),
                "최소IAT(ms)": round(float(row[2]), 3), "고유ID수": int(row[3]),
                "공격유형(예측)": CLASS_NAMES[sub]}
    return {"threat": "can_injection" if detected else "nominal", "detected": detected,
            "score": round(float(probs[first].max()), 3), "latency": None, "latency_unit": "",
            "subtype": CLASS_NAMES[sub], "evidence": evidence, "reasons": reasons,
            "detector": "경량 MLP(윈도 특징)"}
