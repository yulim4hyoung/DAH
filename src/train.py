"""탐지기 학습·평가 진입점.

사용:
  python src/train.py --scenario a2_gnss  --docs-dir "…/dev_docu"
  python src/train.py --scenario b2_satcom --docs-dir "…/dev_docu"
  python src/train.py --scenario b3_can    --docs-dir "…/dev_docu"
  python src/train.py --scenario all       --docs-dir "…/dev_docu"

각 시나리오는 지표표(metrics.md)·그림(*.png)·run_meta.json·모델가중치를 남긴다.
"""
from __future__ import annotations
import os
import sys
import argparse

# 레포 루트(dev/)를 import 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
import matplotlib.pyplot as plt
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                             confusion_matrix, roc_curve, auc)

from src.paths import load_config, models_dir, resolve_docs_dir
from src.io_utils import (new_console, set_seed, save_fig, save_json,
                          save_metrics_md, save_console_log, md_table)
from src import mapping


# ----------------------------- 공통 그림 헬퍼 -----------------------------
def plot_confusion(cm, class_names, title):
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(class_names))); ax.set_xticklabels(class_names)
    ax.set_yticks(range(len(class_names))); ax.set_yticklabels(class_names)
    ax.set_xlabel("예측"); ax.set_ylabel("실제"); ax.set_title(title)
    thresh = cm.max() / 2 if cm.max() else 0.5
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, int(cm[i, j]), ha="center",
                    color="white" if cm[i, j] > thresh else "black")
    ax.grid(False); fig.colorbar(im, fraction=0.046, pad=0.04)
    return fig


def plot_roc(fpr, tpr, roc_auc, title):
    fig, ax = plt.subplots(figsize=(4.8, 4.0))
    ax.plot(fpr, tpr, lw=2, label=f"AUC = {roc_auc:.3f}")
    ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title(title); ax.legend(loc="lower right")
    return fig


# ---------------------- SLA(가용성) 트레이드오프 헬퍼 ----------------------
def sla_sweep(conf_all, y_all, high_conf, thresholds):
    """탐지 임계별 (임계, TPR, 경보율, 서비스방해_일괄차단, 서비스방해_신뢰도게이팅).

    서비스방해율 = 방어자가 '가용성을 깎는 대응'을 하는 평균 강도(0~1)를 운영 트래픽에서 측정.
      일괄차단 정책 : 경보가 뜨면 무조건 강제 차단 → 경보율 × w_aggr(=1.0)
      게이팅 정책   : 신뢰도<high 경보는 서비스 유지형 완화(w_graceful=0.2), 이상은 차단(w_aggr)
    즉 SLA(가용성) 관점에서 '탐지는 유지하되 서비스 중단은 줄이는' 게이팅의 이득을 보인다.
    (정탐이라도 강제 차단은 가용성을 깎으므로 경보 전체를 방해 대상으로 본다.)
    """
    conf = np.asarray(conf_all, dtype=float)
    y = np.asarray(y_all)
    pos = conf[y == 1]
    w_g = mapping.DISRUPTION_WEIGHT["graceful"]
    w_a = mapping.DISRUPTION_WEIGHT["aggressive"]
    rows = []
    for t in thresholds:
        tpr = float((pos >= t).mean()) if len(pos) else 0.0
        alarm = conf >= t
        rate = float(alarm.mean())
        hi = conf >= high_conf
        dis_aggr = rate * w_a
        dis_gate = float((alarm & hi).mean() * w_a + (alarm & ~hi).mean() * w_g)
        rows.append((float(t), tpr, rate, dis_aggr, dis_gate))
    return rows


def plot_sla_tradeoff(rows, high_conf, title):
    ts = [r[0] for r in rows]
    tpr = [r[1] for r in rows]; da = [r[3] for r in rows]; dg = [r[4] for r in rows]
    fig, ax = plt.subplots(figsize=(5.8, 3.9))
    ax.plot(ts, tpr, color="tab:blue", lw=2, marker="o", ms=3, label="공격 탐지율(TPR·유지)")
    ax.plot(ts, da, color="tab:red", lw=2, marker="s", ms=3, label="서비스 방해율(강제차단 일괄)")
    ax.plot(ts, dg, color="tab:green", lw=2, marker="^", ms=3, label="서비스 방해율(신뢰도 게이팅)")
    ax.fill_between(ts, dg, da, color="tab:green", alpha=0.12)
    ax.axvline(high_conf, color="gray", ls=":", lw=1)
    ax.text(high_conf, 1.02, f" high={high_conf}", color="gray", fontsize=8, va="top")
    ax.set_xlabel("탐지 임계 (confidence)"); ax.set_ylabel("비율 (0~1)")
    ax.set_title(title); ax.legend(fontsize=8, loc="center right")
    ax.set_ylim(-0.02, 1.08)
    return fig


def sla_table(rows, picks=(0.5, 0.7, 0.9)):
    """대표 임계 몇 개로 SLA 트레이드오프 md 표 생성."""
    body = []
    for p in picks:
        r = min(rows, key=lambda x: abs(x[0] - p))
        body.append([f"{r[0]:.2f}", f"{r[1]:.3f}", f"{r[2]:.3f}",
                     f"{r[3]:.3f}", f"{r[4]:.3f}"])
    return md_table(["임계", "공격탐지율", "경보율", "서비스방해(일괄차단)", "서비스방해(게이팅)"], body)


# ----------------------------- A2: GNSS -----------------------------
def train_gnss(cfg, docs_dir, console):
    from src.sim.gnss_sim import (generate_dataset, generate_flight, CLASS_NAMES,
                                  FEATURES)
    from src.detect import gnss_cnn as M

    key = "a2_gnss"
    console.rule("[bold cyan]A2 · GNSS 스푸핑/재밍 탐지 (⑦)")
    rng = np.random.default_rng(cfg["seed"])

    console.print("합성 데이터 생성 중…")
    X, y, meta = generate_dataset(cfg, rng)
    # split 70/15/15
    idx = rng.permutation(len(y))
    n1, n2 = int(0.7 * len(y)), int(0.85 * len(y))
    tr, va, te = idx[:n1], idx[n1:n2], idx[n2:]
    console.print(f"윈도 {len(y):,}개 · 학습 {len(tr):,}/검증 {len(va):,}/시험 {len(te):,}")

    model, scaler, hist = M.train_model(X[tr], y[tr], X[va], y[va], cfg)
    console.print(f"학습 완료 · 검증 정확도 {hist[-1]['val_acc']:.3f}")

    # ---- 시험셋 평가 ----
    probs = M.predict_proba(model, scaler, X[te])
    pred = probs.argmax(1)
    yte = y[te]
    acc = accuracy_score(yte, pred)
    p, r, f1, _ = precision_recall_fscore_support(yte, pred, labels=[0, 1, 2],
                                                  zero_division=0)
    cm = confusion_matrix(yte, pred, labels=[0, 1, 2])

    # 이진(공격 vs 정상) ROC
    y_bin = (yte != 0).astype(int)
    attack_score = 1.0 - probs[:, 0]
    fpr, tpr, _ = roc_curve(y_bin, attack_score)
    roc_auc = auc(fpr, tpr)
    # 0.5 임계 TPR/FPR
    pred_bin = (attack_score > 0.5).astype(int)
    tp = int(((pred_bin == 1) & (y_bin == 1)).sum()); fn = int(((pred_bin == 0) & (y_bin == 1)).sum())
    fp = int(((pred_bin == 1) & (y_bin == 0)).sum()); tn = int(((pred_bin == 0) & (y_bin == 0)).sum())
    tpr05 = tp / (tp + fn + 1e-9); fpr05 = fp / (fp + tn + 1e-9)

    # ---- SLA 트레이드오프(신뢰도 게이팅 vs 일괄차단) ----
    sla_thr = np.linspace(0.3, 0.95, 14)
    sla_rows = sla_sweep(attack_score, y_bin, mapping.HIGH_CONFIDENCE, sla_thr)

    # ---- 탐지지연(점진 표류 조기탐지) ----
    W = cfg["gnss"]["window"]; ep = cfg["gnss"]["epochs"]
    lat = {"spoof": [], "jam": []}
    example = None
    for kind in ("spoof", "jam"):
        for _ in range(60):
            feat, labels, onset = generate_flight(kind, ep, rng, W)
            eidx, _pred, aprob = M.score_flight(model, scaler, feat, W)
            aprob = np.array(aprob); eidx = np.array(eidx)
            after = eidx >= onset
            hit = np.where(after & (aprob > 0.5))[0]
            if len(hit):
                lat[kind].append(int(eidx[hit[0]] - onset))
            if kind == "spoof" and example is None:
                example = (feat, labels, onset, eidx, aprob)
    med_spoof = float(np.median(lat["spoof"])) if lat["spoof"] else float("nan")
    med_jam = float(np.median(lat["jam"])) if lat["jam"] else float("nan")
    det_rate_spoof = len(lat["spoof"]) / 60.0
    console.print(f"탐지지연(중앙값) 스푸핑 {med_spoof:.1f}s · 재밍 {med_jam:.1f}s")

    # ---- 그림 ----
    save_fig(plot_confusion(cm, CLASS_NAMES, "GNSS 탐지 혼동행렬"), key,
             "confusion_matrix.png", docs_dir)
    save_fig(plot_roc(fpr, tpr, roc_auc, "GNSS 공격 탐지 ROC (공격 vs 정상)"), key,
             "roc_attack.png", docs_dir)
    # 탐지지연 히스토그램
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    ax.hist(lat["spoof"], bins=range(0, 40, 2), alpha=0.7, label="스푸핑")
    ax.hist(lat["jam"], bins=range(0, 40, 2), alpha=0.7, label="재밍")
    ax.set_xlabel("탐지지연 (초, 공격개시→첫 경보)"); ax.set_ylabel("빈도")
    ax.set_title("GNSS 스푸핑/재밍 탐지지연 분포"); ax.legend()
    save_fig(fig, key, "detection_latency.png", docs_dir)
    save_fig(plot_sla_tradeoff(sla_rows, mapping.HIGH_CONFIDENCE,
             "GNSS SLA 트레이드오프 (탐지율 vs 서비스방해)"), key, "sla_tradeoff.png", docs_dir)
    # 시계열 예시(스푸핑 점진 표류)
    if example:
        feat, labels, onset, eidx, aprob = example
        fig, ax1 = plt.subplots(figsize=(6.4, 3.8))
        t = np.arange(len(feat))
        ax1.plot(t, feat[:, 3], color="tab:red", label="INS 잔차(m)")
        ax1.plot(t, feat[:, 0], color="tab:blue", alpha=0.6, label="C/N0(dB-Hz)")
        ax1.axvline(onset, color="black", ls="--", lw=1, label="공격개시")
        ax2 = ax1.twinx()
        ax2.plot(eidx, aprob, color="tab:green", lw=1.5, label="공격확률")
        ax2.set_ylim(0, 1.05); ax2.set_ylabel("공격확률")
        hit = np.where((np.array(eidx) >= onset) & (np.array(aprob) > 0.5))[0]
        if len(hit):
            ax1.axvline(eidx[hit[0]], color="tab:green", ls=":", lw=1.5, label="탐지시점")
        ax1.set_xlabel("에폭(초)"); ax1.set_ylabel("잔차 / C/N0")
        ax1.set_title("스푸핑 점진 표류 vs 탐지시점")
        ax1.legend(loc="upper left", fontsize=8)
        save_fig(fig, key, "timeseries_example.png", docs_dir)

    # ---- metrics.md (붙여넣기용) ----
    perclass = md_table(["클래스", "Precision", "Recall", "F1"],
                        [[CLASS_NAMES[i], f"{p[i]:.3f}", f"{r[i]:.3f}", f"{f1[i]:.3f}"]
                         for i in range(3)])
    summary = md_table(["지표", "값"], [
        ["전체 정확도", f"{acc:.3f}"],
        ["공격탐지 AUC(공격 vs 정상)", f"{roc_auc:.3f}"],
        ["TPR@0.5", f"{tpr05:.3f}"],
        ["FPR@0.5", f"{fpr05:.3f}"],
        ["탐지지연 중앙값(스푸핑)", f"{med_spoof:.1f} s"],
        ["탐지지연 중앙값(재밍)", f"{med_jam:.1f} s"],
        ["스푸핑 탐지율", f"{det_rate_spoof:.2f}"],
    ])
    save_metrics_md(key, "A2 · GNSS 스푸핑/재밍 탐지 — 지표", [
        ("요약", summary),
        ("클래스별 성능", perclass),
        ("SLA 트레이드오프(가용성)", sla_table(sla_rows) + "\n\n"
         "> 신뢰도 게이팅: 신뢰도<0.7 경보는 서비스 유지형 완화(방해 0.2), 이상은 강제 차단(방해 1.0).\n"
         "> 단, 본 DNN은 확신이 포화(경보 대부분 신뢰도≥0.9)라 게이팅 발동이 드물어 이 데이터에선 "
         "게이팅과 일괄차단의 격차가 작다 — 게이팅의 이득은 탐지가 불확실한 실환경/저품질 신호에서 커진다."),
        ("그림", "- `confusion_matrix.png` 혼동행렬\n- `roc_attack.png` 공격탐지 ROC\n"
                 "- `detection_latency.png` 탐지지연 분포\n- `timeseries_example.png` 점진 표류 vs 탐지시점\n"
                 "- `sla_tradeoff.png` SLA 트레이드오프(탐지율 vs 서비스방해)"),
        ("비고", f"모델 1D-CNN · 특징 {FEATURES} · 윈도 {W}s · 합성데이터(시드 {cfg['seed']}).\n"
                 "TEXBAT/OAKBAT 실데이터 연동은 향후과제."),
    ], docs_dir)

    sla05 = min(sla_rows, key=lambda x: abs(x[0] - 0.5))
    meta.update({"test_accuracy": acc, "auc_attack": float(roc_auc),
                 "tpr@0.5": tpr05, "fpr@0.5": fpr05,
                 "median_latency_spoof_s": med_spoof, "median_latency_jam_s": med_jam,
                 "per_class_f1": {CLASS_NAMES[i]: float(f1[i]) for i in range(3)},
                 "sla_cost_aggressive@0.5": sla05[3], "sla_cost_gated@0.5": sla05[4],
                 "hyperparams": cfg["gnss"]["cnn"], "seed": cfg["seed"]})
    save_json(key, "run_meta.json", meta, docs_dir)

    # ---- 모델 저장 ----
    torch.save({"state_dict": model.state_dict(), "scaler": scaler,
                "channels": cfg["gnss"]["cnn"]["channels"]},
               os.path.join(models_dir(cfg), "a2_gnss.pt"))
    save_console_log(console, key, "run_log.txt", docs_dir)
    console.print(f"[green]A2 완료[/] · 정확도 {acc:.3f} · AUC {roc_auc:.3f}")
    return {"scenario": key, "accuracy": acc, "auc": float(roc_auc)}


def train_satcom(cfg, docs_dir, console):
    from src.sim.satcom_sim import generate_dataset, FEATURES
    from src.detect import satcom_ae as M

    key = "b2_satcom"
    console.rule("[bold cyan]B2 · SATCOM 관리망 이상탐지 (⑤, AcidRain형)")
    rng = np.random.default_rng(cfg["seed"])

    console.print("합성 NOC 트래픽 생성 중…")
    Xtr, Xte, yte, atk_windows, meta = generate_dataset(cfg, rng)
    console.print(f"정상 학습버킷 {len(Xtr):,} · 시험버킷 {len(Xte):,} "
                  f"(공격비율 {yte.mean():.2f})")

    model, scaler, thr, hist = M.train_ae(Xtr, cfg)
    console.print(f"오토인코더 학습 완료 · 임계(정상 {cfg['satcom']['ae']['threshold_pct']}%tile) {thr:.4f}")

    # ---- 평가 ----
    err = M.recon_error(model, scaler, Xte)
    fpr, tpr, _ = roc_curve(yte, err)
    roc_auc = auc(fpr, tpr)
    pred = (err > thr).astype(int)
    p, r, f1, _ = precision_recall_fscore_support(yte, pred, average="binary", zero_division=0)
    tp = int(((pred == 1) & (yte == 1)).sum()); fn = int(((pred == 0) & (yte == 1)).sum())
    fp = int(((pred == 1) & (yte == 0)).sum()); tn = int(((pred == 0) & (yte == 0)).sum())
    tpr_thr = tp / (tp + fn + 1e-9); fpr_thr = fp / (fp + tn + 1e-9)

    # ---- SLA 트레이드오프 ----
    conf_all = np.clip(err / (2 * thr + 1e-9), 0, 1)  # 임계 2배 오차=신뢰도 1.0
    sla_thr = np.linspace(0.3, 0.95, 14)
    sla_rows = sla_sweep(conf_all, yte, mapping.HIGH_CONFIDENCE, sla_thr)

    # ---- 탐지지연(대량 배포 조기차단) ----
    lat = []
    example = None
    for feat, labels, onset in atk_windows:
        e = M.recon_error(model, scaler, feat)
        hit = np.where((np.arange(len(feat)) >= onset) & (e > thr))[0]
        if len(hit):
            lat.append(int(hit[0] - onset))
        if example is None:
            example = (feat, labels, onset, e)
    med_lat = float(np.median(lat)) if lat else float("nan")
    det_rate = len(lat) / len(atk_windows)
    console.print(f"탐지지연 중앙값 {med_lat:.1f} 버킷 · 공격윈도 탐지율 {det_rate:.2f}")

    # ---- 그림 ----
    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    ax.hist(err[yte == 0], bins=40, alpha=0.7, label="정상", color="tab:blue", density=True)
    ax.hist(err[yte == 1], bins=40, alpha=0.7, label="공격", color="tab:red", density=True)
    ax.axvline(thr, color="black", ls="--", lw=1.5, label="임계")
    ax.set_xlabel("재구성 오차(MSE)"); ax.set_ylabel("밀도")
    ax.set_title("SATCOM 정상 vs 공격 재구성오차 분포"); ax.legend()
    try:
        ax.set_xlim(0, np.percentile(err, 99.5))
    except Exception:
        pass
    save_fig(fig, key, "recon_error_hist.png", docs_dir)

    save_fig(plot_roc(fpr, tpr, roc_auc, "SATCOM 이상탐지 ROC"), key, "roc.png", docs_dir)
    save_fig(plot_sla_tradeoff(sla_rows, mapping.HIGH_CONFIDENCE,
             "SATCOM SLA 트레이드오프 (탐지율 vs 서비스방해)"), key, "sla_tradeoff.png", docs_dir)

    if example:
        feat, labels, onset, e = example
        b = np.arange(len(feat))
        fig, ax1 = plt.subplots(figsize=(6.6, 3.8))
        ax1.plot(b, feat[:, 2], color="tab:orange", label="펌웨어 푸시")
        ax1.plot(b, feat[:, 6], color="tab:red", label="모뎀 오프라인")
        ax1.plot(b, feat[:, 3], color="tab:purple", alpha=0.5, label="대상 모뎀 수")
        ax1.axvline(onset, color="black", ls="--", lw=1, label="공격개시")
        ax2 = ax1.twinx()
        ax2.plot(b, e, color="tab:green", lw=1.5, label="재구성오차")
        ax2.axhline(thr, color="tab:green", ls=":", lw=1)
        hit = np.where((b >= onset) & (e > thr))[0]
        if len(hit):
            ax1.axvline(b[hit[0]], color="tab:green", ls=":", lw=1.5, label="탐지시점")
        ax1.set_xlabel("버킷(분)"); ax1.set_ylabel("이벤트 수"); ax2.set_ylabel("재구성오차")
        ax1.set_title("AcidRain형 공격 전개 vs 탐지시점")
        ax1.legend(loc="upper left", fontsize=8)
        save_fig(fig, key, "timeline_example.png", docs_dir)

    # ---- metrics.md ----
    summary = md_table(["지표", "값"], [
        ["이상탐지 AUC", f"{roc_auc:.3f}"],
        ["Precision", f"{p:.3f}"], ["Recall(TPR)", f"{r:.3f}"], ["F1", f"{f1:.3f}"],
        ["FPR@임계", f"{fpr_thr:.3f}"],
        ["탐지지연 중앙값", f"{med_lat:.1f} 버킷(분)"],
        ["공격윈도 탐지율", f"{det_rate:.2f}"],
    ])
    save_metrics_md(key, "B2 · SATCOM 관리망 이상탐지 — 지표", [
        ("요약", summary),
        ("SLA 트레이드오프(가용성)", sla_table(sla_rows) + "\n\n"
         "> 신뢰도 게이팅(신뢰도<0.7 완화)이 관리망 오차단으로 인한 BLOS 링크 중단을 낮춘다."),
        ("그림", "- `recon_error_hist.png` 정상 vs 공격 재구성오차 분포+임계\n"
                 "- `roc.png` 이상탐지 ROC\n- `timeline_example.png` AcidRain형 전개 vs 탐지시점\n"
                 "- `sla_tradeoff.png` SLA 트레이드오프"),
        ("비고", f"비지도 오토인코더(정상만 학습) · 특징 {FEATURES}.\n"
                 f"임계=정상 재구성오차 {cfg['satcom']['ae']['threshold_pct']}%tile. 합성데이터(시드 {cfg['seed']})."),
    ], docs_dir)

    sla05 = min(sla_rows, key=lambda x: abs(x[0] - 0.5))
    meta.update({"auc": float(roc_auc), "precision": float(p), "recall": float(r),
                 "f1": float(f1), "fpr@thr": fpr_thr, "threshold": thr,
                 "median_latency_buckets": med_lat, "detection_rate": det_rate,
                 "sla_cost_aggressive@0.5": sla05[3], "sla_cost_gated@0.5": sla05[4],
                 "hyperparams": cfg["satcom"]["ae"], "seed": cfg["seed"]})
    save_json(key, "run_meta.json", meta, docs_dir)

    torch.save({"state_dict": model.state_dict(), "scaler": scaler, "threshold": thr,
                "hp": cfg["satcom"]["ae"]},
               os.path.join(models_dir(cfg), "b2_satcom.pt"))
    save_console_log(console, key, "run_log.txt", docs_dir)
    console.print(f"[green]B2 완료[/] · AUC {roc_auc:.3f} · F1 {f1:.3f}")
    return {"scenario": key, "auc": float(roc_auc), "f1": float(f1)}


def train_can(cfg, docs_dir, console):
    from src.sim.can_loader import generate_windows, CLASS_NAMES, FEATURES
    from src.detect import can_ids as M
    from src.paths import data_dir

    key = "b3_can"
    console.rule("[bold cyan]B3 · CAN 침입탐지 (⑧)")
    rng = np.random.default_rng(cfg["seed"])

    X, y, source = generate_windows(cfg, rng, data_root=data_dir())
    console.print(f"데이터 출처: [bold]{source}[/] · 윈도 {len(y):,}개 "
                  f"(클래스 {np.bincount(y).tolist()})")

    idx = rng.permutation(len(y))
    n1, n2 = int(0.7 * len(y)), int(0.85 * len(y))
    tr, va, te = idx[:n1], idx[n1:n2], idx[n2:]
    model, scaler, hist = M.train_model(X[tr], y[tr], X[va], y[va], cfg)
    console.print(f"학습 완료 · 검증 정확도 {hist[-1]['val_acc']:.3f}")

    probs = M.predict(model, scaler, X[te]); pred = probs.argmax(1); yte = y[te]
    acc = accuracy_score(yte, pred)
    p, r, f1, _ = precision_recall_fscore_support(yte, pred, labels=[0, 1, 2, 3],
                                                  zero_division=0)
    macro_f1 = float(np.mean(f1))
    cm = confusion_matrix(yte, pred, labels=[0, 1, 2, 3])
    # 공격 vs 정상 ROC
    y_bin = (yte != 0).astype(int); attack_score = 1.0 - probs[:, 0]
    fpr, tpr, _ = roc_curve(y_bin, attack_score); roc_auc = auc(fpr, tpr)
    console.print(f"정확도 {acc:.3f} · macro-F1 {macro_f1:.3f} · 공격탐지 AUC {roc_auc:.3f}")

    # ---- SLA 트레이드오프 ----
    sla_thr = np.linspace(0.3, 0.95, 14)
    sla_rows = sla_sweep(attack_score, y_bin, mapping.HIGH_CONFIDENCE, sla_thr)

    # ---- 그림 ----
    save_fig(plot_confusion(cm, CLASS_NAMES, "CAN 침입탐지 혼동행렬"), key,
             "confusion_matrix.png", docs_dir)
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    ax.bar(CLASS_NAMES, f1, color=["tab:gray", "tab:red", "tab:orange", "tab:purple"])
    ax.set_ylim(0, 1.05); ax.set_ylabel("F1"); ax.set_title("CAN 클래스별 F1")
    for i, v in enumerate(f1):
        ax.text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=9)
    save_fig(fig, key, "per_class_f1.png", docs_dir)
    save_fig(plot_roc(fpr, tpr, roc_auc, "CAN 공격 탐지 ROC (공격 vs 정상)"), key,
             "roc_attack.png", docs_dir)
    save_fig(plot_sla_tradeoff(sla_rows, mapping.HIGH_CONFIDENCE,
             "CAN SLA 트레이드오프 (탐지율 vs 서비스방해)"), key, "sla_tradeoff.png", docs_dir)

    # ---- metrics.md ----
    perclass = md_table(["클래스", "Precision", "Recall", "F1"],
                        [[CLASS_NAMES[i], f"{p[i]:.3f}", f"{r[i]:.3f}", f"{f1[i]:.3f}"]
                         for i in range(4)])
    summary = md_table(["지표", "값"], [
        ["전체 정확도", f"{acc:.3f}"], ["macro-F1", f"{macro_f1:.3f}"],
        ["공격탐지 AUC", f"{roc_auc:.3f}"], ["데이터 출처", source],
    ])
    save_metrics_md(key, "B3 · CAN 침입탐지 — 지표", [
        ("요약", summary),
        ("클래스별 성능", perclass),
        ("SLA 트레이드오프(가용성)", sla_table(sla_rows) + "\n\n"
         "> 신뢰도 게이팅(신뢰도<0.7 완화)이 오탐으로 인한 차량 정지(구동계 차단)를 낮춘다."),
        ("그림", "- `confusion_matrix.png` 4클래스 혼동행렬\n- `per_class_f1.png` 클래스별 F1\n"
                 "- `roc_attack.png` 공격탐지 ROC\n- `sla_tradeoff.png` SLA 트레이드오프"),
        ("비고", f"경량 MLP · 윈도 특징 {FEATURES}.\n데이터: {source} "
                 f"(실 Car-Hacking CSV를 data/can/ 에 두면 자동 사용, 없으면 동형 합성)."),
    ], docs_dir)

    sla05 = min(sla_rows, key=lambda x: abs(x[0] - 0.5))
    meta = {"source": source, "n_windows": int(len(y)),
            "class_counts": np.bincount(y).tolist(), "test_accuracy": acc,
            "macro_f1": macro_f1, "auc_attack": float(roc_auc),
            "per_class_f1": {CLASS_NAMES[i]: float(f1[i]) for i in range(4)},
            "sla_cost_aggressive@0.5": sla05[3], "sla_cost_gated@0.5": sla05[4],
            "features": FEATURES, "hyperparams": cfg["can"]["mlp"], "seed": cfg["seed"]}
    save_json(key, "run_meta.json", meta, docs_dir)

    torch.save({"state_dict": model.state_dict(), "scaler": scaler,
                "hp": cfg["can"]["mlp"]}, os.path.join(models_dir(cfg), "b3_can.pt"))
    save_console_log(console, key, "run_log.txt", docs_dir)
    console.print(f"[green]B3 완료[/] · 정확도 {acc:.3f} · macro-F1 {macro_f1:.3f}")
    return {"scenario": key, "accuracy": acc, "macro_f1": macro_f1, "source": source}


def train_gnss_hardened(cfg, console):
    """적응형 공격 프로파일(회피형 slow_creep 포함)을 혼합해 hardened 모델을 추가 학습.

    기본 a2_gnss.pt(baseline)는 건드리지 않고 a2_gnss_hardened.pt로 별도 저장.
    eval_adaptive.py가 baseline vs hardened를 비교하는 데 쓴다.
    """
    from src.sim.gnss_sim import generate_dataset
    from src.detect import gnss_cnn as M

    console.rule("[bold cyan]A2-hardened · 적응형 프로파일 혼합 재학습")
    rng = np.random.default_rng(cfg["seed"] + 777)
    profiles = ["trained", "slow_creep", "aggressive"]
    X, y, meta = generate_dataset(cfg, rng, spoof_profiles=profiles)
    idx = rng.permutation(len(y))
    n1, n2 = int(0.7 * len(y)), int(0.85 * len(y))
    tr, va = idx[:n1], idx[n1:n2]
    model, scaler, hist = M.train_model(X[tr], y[tr], X[va], y[va], cfg)
    torch.save({"state_dict": model.state_dict(), "scaler": scaler,
                "channels": cfg["gnss"]["cnn"]["channels"], "profiles": profiles},
               os.path.join(models_dir(cfg), "a2_gnss_hardened.pt"))
    console.print(f"[green]A2-hardened 저장[/] · 검증 정확도 {hist[-1]['val_acc']:.3f} "
                  f"· 혼합 프로파일 {profiles}")


DISPATCH = {"a2_gnss": train_gnss, "b2_satcom": train_satcom, "b3_can": train_can}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="all",
                    choices=["a2_gnss", "b2_satcom", "b3_can", "all"])
    ap.add_argument("--docs-dir", default=None, help="보고서 근거자료 저장 폴더(dev_docu)")
    ap.add_argument("--adaptive-train", action="store_true",
                    help="적응형 프로파일 혼합 hardened GNSS 모델 추가 학습(a2_gnss_hardened.pt)")
    args = ap.parse_args()

    cfg = load_config()
    set_seed(cfg["seed"])
    docs_dir = resolve_docs_dir(args.docs_dir)
    console = new_console()

    keys = ["a2_gnss", "b2_satcom", "b3_can"] if args.scenario == "all" else [args.scenario]
    results = []
    for k in keys:
        try:
            results.append(DISPATCH[k](cfg, docs_dir, console))
        except NotImplementedError:
            console.print(f"[yellow]{k}: 아직 미구현(스킵)")
    if args.adaptive_train and "a2_gnss" in keys:
        train_gnss_hardened(cfg, console)
    console.rule("[bold]학습 요약")
    for rslt in results:
        console.print(rslt)


if __name__ == "__main__":
    main()
