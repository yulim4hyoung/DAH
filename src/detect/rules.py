"""규칙 기반 베이스라인 — 설명가능한 1차 판정(통합본 Part 6 §15).

DNN과 병행해 '왜 이상인지'를 사람이 읽을 수 있는 근거로 제시한다.
각 함수는 (flag: bool, reasons: list[str]) 반환.
"""
from __future__ import annotations
import numpy as np


def gnss_rule(feat_row) -> tuple[bool, list[str]]:
    """feat_row = [cn0_mean, cn0_std, agc, ins_residual, dop, clock_jump, num_sats]."""
    cn0, cn0_std, agc, res, dop, clk, sats = feat_row
    r = []
    if res > 15:
        r.append(f"GNSS-INS 잔차 {res:.0f} m > 15 m (RAIM 무결성 임계 초과)")
    if sats < 6 or cn0 < 30:
        r.append(f"C/N0 {cn0:.0f} dB-Hz·위성 {int(sats)}기 — 신호 붕괴(재밍 징후)")
    if cn0_std < 1.6 and agc < 0.42:
        r.append("C/N0 비정상 균일 + AGC 하강 — 스푸퍼 강신호 정황")
    if dop < 1.5:
        r.append(f"DOP {dop:.2f} 비정상적으로 낮음(위조 신호 정황)")
    return (len(r) > 0, r)


def satcom_rule(bucket) -> tuple[bool, list[str]]:
    """bucket = [cmd_rate, entropy, fw_push, distinct_modems, auth_fail,
                 config_change, modems_offline, offhours]."""
    rate, ent, fw, modems, auth, cfg, offl, night = bucket
    r = []
    if auth >= 3:
        r.append(f"인증 실패 {auth:.0f}건 — 관리망 비인가 접근(VPN 이상)")
    if fw >= 3:
        r.append(f"펌웨어 푸시 {fw:.0f}건 — 대량 배포 정황")
    if modems > 30:
        r.append(f"대상 모뎀 {modems:.0f}대 — 비정상 대량 팬아웃")
    if offl >= 5:
        r.append(f"모뎀 동시 오프라인 {offl:.0f}대 — 와이퍼 효과 정황")
    return (len(r) > 0, r)


def can_rule(feat_row) -> tuple[bool, list[str]]:
    """feat_row = [mean_iat, std_iat, min_iat, n_unique, max_id_freq,
                   id_entropy, known_ratio, mean_dlc]."""
    miat, siat, mn, nuniq, maxfreq, ent, known, dlc = feat_row
    r = []
    if known < 0.9:
        r.append(f"미등록 CAN ID 비율 {(1-known):.0%} — 퍼지/주입 정황")
    if maxfreq > 0.5:
        r.append(f"단일 ID 점유율 {maxfreq:.0%} — DoS/스푸핑 정황")
    if mn < 0.05:
        r.append(f"최소 IAT {mn:.3f} ms — 버스 폭주(DoS) 정황")
    return (len(r) > 0, r)
