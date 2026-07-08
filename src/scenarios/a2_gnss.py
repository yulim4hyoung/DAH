"""시나리오 A2 — GNSS 스푸핑(점진 표류). 계층 ⑦."""
from __future__ import annotations
import os
import numpy as np
import torch

from ..paths import load_config, models_dir
from ..sim.gnss_sim import generate_flight, CLASS_NAMES, FEATURES
from ..detect.gnss_cnn import GnssCNN, score_flight
from ..detect.rules import gnss_rule

KEY = "a2_gnss"
TITLE = "GNSS 스푸핑 — 점진 표류로 항로 탈취"
LAYER = "⑦ PNT"
PERSPECTIVE = "COTS·군용 공통 · GPS L1/L2/L5"
THREAT = "gnss_spoofing"
KILLCHAIN = [
    ("1 신호탐지", "대상 GNSS 대역·수신기 특성 파악", "SDR 스캔"),
    ("2 프로토콜분석", "L1 C/A 전문·확산코드(공개) 구조 분석", "GNSS-SDR"),
    ("3 취약점분석", "무인증·약전력 확인, INS/OSNMA 사용여부 점검", "수신기 로그"),
    ("4 코드생성", "동기→점진 표류 위조 항법해 생성", "gps-sdr-sim(차폐)"),
    ("5 침투", "진짜 신호 동기 후 전력 우위로 락온 인계", "SDR TX(차폐)"),
    ("6 무력화", "점진 표류로 항로 이탈·강제착륙/포획", "—"),
]
TARGET = "GNSS 의존 UAV(민간 L1 C/A 단독, INS 융합 미흡, OSNMA 미사용)"


def load():
    d = torch.load(os.path.join(models_dir(), "a2_gnss.pt"), weights_only=False)
    m = GnssCNN(ch=d["channels"]); m.load_state_dict(d["state_dict"]); m.eval()
    return {"model": m, "scaler": d["scaler"]}


def attack(rng):
    cfg = load_config()
    ep, w = cfg["gnss"]["epochs"], cfg["gnss"]["window"]
    feat, labels, onset = generate_flight("spoof", ep, rng, w)
    return {"kind": "spoof", "feat": feat, "onset": onset, "window": w}


def detect(bundle, atk):
    feat, onset, w = atk["feat"], atk["onset"], atk["window"]
    idx, pred, aprob = score_flight(bundle["model"], bundle["scaler"], feat, w)
    idx, aprob = np.array(idx), np.array(aprob)
    after = idx >= onset
    hit = np.where(after & (aprob > 0.5))[0]
    detected = len(hit) > 0
    det_epoch = int(idx[hit[0]]) if detected else int(idx[-1])
    latency = det_epoch - onset if detected else None
    cls = pred[hit[0]] if detected else 0
    threat = {0: "nominal", 1: "gnss_spoofing", 2: "gnss_jamming"}[int(cls)]
    row = feat[det_epoch]
    _, reasons = gnss_rule(row)
    evidence = {"C/N0(dB-Hz)": round(float(row[0]), 1),
                "INS 잔차(m)": round(float(row[3]), 1),
                "AGC": round(float(row[2]), 2),
                "DOP": round(float(row[4]), 2),
                "위성수": int(row[6])}
    return {"threat": threat, "detected": detected,
            "score": round(float(aprob[hit[0]]) if detected else float(aprob.max()), 3),
            "latency": latency, "latency_unit": "초", "det_epoch": det_epoch, "onset": onset,
            "evidence": evidence, "reasons": reasons, "detector": "1D-CNN(다특징 시계열)"}
