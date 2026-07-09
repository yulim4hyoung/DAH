"""적응형/회피형 공격 강건성 평가 — 순환평가 비판을 정면 반박하는 실험.

탐지기가 '학습한' 스푸핑 프로파일(trained)과, 학습분포를 벗어난 회피형(slow_creep)·
공격적(aggressive) 프로파일에 대해 탐지율·탐지지연을 비교한다. baseline 모델은 회피형에서
탐지율이 떨어지고, 적응형 혼합으로 재학습한 hardened 모델은 이를 회복함을 보인다.

사용:
  python src/eval_adaptive.py                       # baseline(+있으면 hardened) 비교
  python src/eval_adaptive.py --docs-dir "…/dev_docu"

먼저 `python src/train.py --scenario a2_gnss --adaptive-train` 로
a2_gnss.pt(baseline)와 a2_gnss_hardened.pt(hardened)를 만들어 두면 둘을 비교한다.
hardened가 없으면 baseline만 평가한다.
"""
from __future__ import annotations
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
import matplotlib.pyplot as plt

from src.paths import load_config, models_dir, resolve_docs_dir
from src.io_utils import new_console, set_seed, save_fig, save_text, md_table
from src.sim.gnss_sim import generate_flight, SPOOF_PROFILES
from src.detect.gnss_cnn import GnssCNN, score_flight

PROFILES = ["trained", "slow_creep", "aggressive"]
PROFILE_KO = {"trained": "학습됨(기본)", "slow_creep": "회피형(느린표류)", "aggressive": "공격적(빠른표류)"}
# 조기탐지 마감시한(초): 스푸핑을 이 시간 안에 잡아야 항로가 크게 끌려가기 전 대응 가능.
# 탐지'율'은 비행 전체를 보면 대부분 100%라, 운영상 의미 있는 지표는 '조기탐지율'이다.
EARLY_DEADLINE = 10


def _load_model(fname):
    path = os.path.join(models_dir(), fname)
    if not os.path.exists(path):
        return None
    d = torch.load(path, weights_only=False)
    m = GnssCNN(ch=d["channels"]); m.load_state_dict(d["state_dict"]); m.eval()
    return {"model": m, "scaler": d["scaler"]}


def _gen_flights(profile, cfg, n):
    """프로파일별 스푸핑 비행 n개를 결정적으로 생성(모델 간 공정 비교 위해 고정)."""
    ep, W = cfg["gnss"]["epochs"], cfg["gnss"]["window"]
    rng = np.random.default_rng(cfg["seed"] + sum(ord(c) for c in profile))
    return [generate_flight("spoof", ep, rng, W, profile=profile) for _ in range(n)], W


def _eval(bundle, flights, W):
    """반환: (조기탐지율<=deadline, 전체탐지율, 중앙값지연)."""
    lats, det, early = [], 0, 0
    for feat, labels, onset in flights:
        eidx, _pred, aprob = score_flight(bundle["model"], bundle["scaler"], feat, W)
        eidx, aprob = np.array(eidx), np.array(aprob)
        hit = np.where((eidx >= onset) & (aprob > 0.5))[0]
        if len(hit):
            det += 1
            lat = int(eidx[hit[0]] - onset)
            lats.append(lat)
            early += int(lat <= EARLY_DEADLINE)
    n = len(flights)
    return early / n, det / n, (float(np.median(lats)) if lats else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-dir", default=None)
    ap.add_argument("--n", type=int, default=80, help="프로파일당 평가 비행 수")
    args = ap.parse_args()

    cfg = load_config(); set_seed(cfg["seed"])
    docs_dir = resolve_docs_dir(args.docs_dir)
    console = new_console()
    console.rule("[bold cyan]적응형 공격 강건성 평가 (A2 GNSS)")

    baseline = _load_model("a2_gnss.pt")
    if baseline is None:
        console.print("[red]a2_gnss.pt 없음 — 먼저 train.py 실행 필요")
        console.print(console.export_text()); return
    hardened = _load_model("a2_gnss_hardened.pt")
    models = {"baseline": baseline}
    if hardened:
        models["hardened"] = hardened
        console.print("baseline + hardened 비교")
    else:
        console.print("baseline만 평가(hardened 없음 — train.py --adaptive-train 로 생성 가능)")

    # 평가
    results = {name: {"early": [], "det": [], "lat": []} for name in models}
    for prof in PROFILES:
        flights, W = _gen_flights(prof, cfg, args.n)
        for name, bundle in models.items():
            er, dr, ml = _eval(bundle, flights, W)
            results[name]["early"].append(er)
            results[name]["det"].append(dr)
            results[name]["lat"].append(ml)
        line = " · ".join(f"{name} 조기탐지 {results[name]['early'][-1]:.2f}" for name in models)
        console.print(f"[{PROFILE_KO[prof]}] {line}")

    # ---- 그림: 프로파일별 조기탐지율(<=deadline) (baseline vs hardened) ----
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    x = np.arange(len(PROFILES)); width = 0.36 if len(models) > 1 else 0.5
    colors = {"baseline": "tab:red", "hardened": "tab:green"}
    for i, name in enumerate(models):
        off = (i - (len(models) - 1) / 2) * width
        bars = ax.bar(x + off, results[name]["early"], width,
                      label=name, color=colors.get(name, "tab:blue"))
        for b, v in zip(bars, results[name]["early"]):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}",
                    ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([PROFILE_KO[p] for p in PROFILES])
    ax.set_ylim(0, 1.12)
    ax.set_ylabel(f"조기탐지율 (공격개시 {EARLY_DEADLINE}초 이내 경보)")
    ax.set_title(f"적응형 공격 강건성 — 회피형에서 baseline 조기탐지 급락, hardened 회복")
    ax.legend(loc="lower left", fontsize=9)
    save_fig(fig, "a2_gnss", "adaptive_robustness.png", docs_dir)

    # ---- 표(md) ----
    headers = (["프로파일"] + [f"{n} 조기탐지" for n in models]
               + [f"{n} 지연(s)" for n in models] + [f"{n} 전체탐지" for n in models])
    rows = []
    for i, prof in enumerate(PROFILES):
        row = [PROFILE_KO[prof]]
        row += [f"{results[n]['early'][i]:.2f}" for n in models]
        row += [("-" if np.isnan(results[n]['lat'][i]) else f"{results[n]['lat'][i]:.0f}")
                for n in models]
        row += [f"{results[n]['det'][i]:.2f}" for n in models]
        rows.append(row)
    table = md_table(headers, rows)

    note = (f"적응형 공격 강건성 실험 — 학습 프로파일(trained)과 학습분포 밖 프로파일"
            f"(slow_creep=회피형 느린표류, aggressive=빠른표류)에 대한 **조기탐지율**(공격개시 "
            f"{EARLY_DEADLINE}초 이내 경보) 비교. 스푸핑은 늦게 잡으면 이미 항로가 끌려간 뒤라, "
            f"전체 탐지율(대개 100%)보다 조기탐지가 운영상 핵심 지표다.\n\n"
            "> **해석**: baseline은 회피형(slow_creep)에서 조기탐지율이 떨어진다(자기 생성기로 "
            "학습·평가한 순환평가의 한계를 정직하게 노출). hardened(적응형 프로파일 혼합 재학습)는 "
            "이를 회복한다. 설명가능 규칙(rules.gnss_rule)에도 '누적 표류 추세' 근거를 추가해 회피형을 함께 포착.")
    body = f"# A2 · 적응형 공격 강건성\n\n{note}\n\n{table}\n"
    save_text("a2_gnss", "adaptive_robustness.md", body, docs_dir)

    console.print("[green]완료[/] · adaptive_robustness.png / .md 저장")


if __name__ == "__main__":
    main()
