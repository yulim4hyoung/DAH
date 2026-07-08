"""시나리오 B2 — SATCOM 관리망·모뎀 침해(AcidRain형). 계층 ⑤."""
from __future__ import annotations
import os
import numpy as np
import torch

from ..paths import load_config, models_dir
from ..sim.satcom_sim import generate_window, FEATURES
from ..detect.satcom_ae import SatcomAE, recon_error
from ..detect.rules import satcom_rule

KEY = "b2_satcom"
TITLE = "SATCOM 관리망·모뎀 침해 — BLOS C2 광역 마비"
LAYER = "⑤ 위성(BLOS)"
PERSPECTIVE = "BLOS 위성단말(모뎀) + 지상 GW/관리망(NOC)"
THREAT = "satcom_wiper"
KILLCHAIN = [
    ("1 신호탐지", "위성 GW/관리망·단말 식별", "OSINT·스캐너"),
    ("2 프로토콜분석", "관리채널·모뎀 펌웨어 갱신 경로 분석", "트래픽 분석"),
    ("3 취약점분석", "관리망 인증부재·무서명 펌웨어 확인", "펌웨어 역분석"),
    ("4 코드생성", "모뎀 손상 페이로드(와이퍼) 제작", "(연구·격리)"),
    ("5 침투", "관리채널 경유 다수 모뎀 일괄 배포", "관리 인터페이스 악용"),
    ("6 무력화", "모뎀 영구손상 → BLOS C2/ISR 광역 마비", "—"),
]
TARGET = "BLOS 위성단말 탑재 UAV + 지상 NOC(경계 VPN 오설정)"


def load():
    d = torch.load(os.path.join(models_dir(), "b2_satcom.pt"), weights_only=False)
    hp = d["hp"]
    m = SatcomAE(hidden=hp["hidden"], bottleneck=hp["bottleneck"])
    m.load_state_dict(d["state_dict"]); m.eval()
    return {"model": m, "scaler": d["scaler"], "threshold": d["threshold"]}


def attack(rng, evasive=False):
    # evasive: 이 시나리오는 회피형 프로파일 미지원(하위호환용 인자, 무시).
    cfg = load_config()
    feat, labels, onset = generate_window("attack", cfg["satcom"]["bucket_len"], rng)
    return {"feat": feat, "onset": onset}


def detect(bundle, atk):
    feat, onset = atk["feat"], atk["onset"]
    err = recon_error(bundle["model"], bundle["scaler"], feat)
    thr = bundle["threshold"]
    b = np.arange(len(feat))
    hit = np.where((b >= onset) & (err > thr))[0]
    detected = len(hit) > 0
    det_b = int(hit[0]) if detected else int(len(feat) - 1)
    latency = det_b - onset if detected else None
    row = feat[det_b]
    _, reasons = satcom_rule(row)
    evidence = {"펌웨어푸시": int(row[2]), "대상모뎀": int(row[3]),
                "인증실패": int(row[4]), "모뎀오프라인": int(row[6]),
                "재구성오차": round(float(err[det_b]), 3), "임계": round(float(thr), 3)}
    ratio = float(err[det_b] / (thr + 1e-9))
    # 신뢰도: 재구성오차가 임계의 2배면 1.0(=확신). 임계 부근이면 0.5.
    conf = max(0.0, min(1.0, ratio / 2.0))
    return {"threat": "satcom_wiper" if detected else "nominal", "detected": detected,
            "score": round(ratio, 2), "confidence": round(conf, 3), "latency": latency,
            "latency_unit": "버킷(분)", "det_epoch": det_b, "onset": onset,
            "evidence": evidence, "reasons": reasons, "detector": "오토인코더(비지도 이상탐지)"}
