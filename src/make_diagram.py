"""SENTINEL 아키텍처 다이어그램(PNG) 생성 — mermaid-cli 없이 matplotlib로.

python src/make_diagram.py --docs-dir "…/dev_docu"  → 00_overview/architecture.png
"""
from __future__ import annotations
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from src.paths import resolve_docs_dir, REPO_ROOT
from src.io_utils import save_fig  # 한글 폰트 세팅 포함


def _box(ax, x, y, w, h, title, lines, fc, ec):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.5, edgecolor=ec, facecolor=fc))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="top",
            fontsize=11, fontweight="bold")
    ax.text(x + w / 2, y + h - 0.62, "\n".join(lines), ha="center", va="top", fontsize=8.5)


def _arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
                                 lw=1.6, color="#444"))


def build():
    fig, ax = plt.subplots(figsize=(12.5, 6.2))
    ax.set_xlim(0, 13); ax.set_ylim(0, 7); ax.axis("off")
    ax.text(6.5, 6.75, "SENTINEL — UAV/UGV 통신보안 멀티에이전트 방어 (DAH 2026)",
            ha="center", fontsize=14, fontweight="bold")

    _box(ax, 0.3, 3.6, 2.6, 2.4, "🔴 공격 에이전트",
         ["Recon → Attacker", "6단계 킬체인", "(시뮬레이션·오프라인)"], "#fde8e8", "#c0392b")
    _box(ax, 3.3, 3.6, 3.0, 2.4, "🟦 시나리오 플러그인",
         ["A2 GNSS 스푸핑 ⑦", "B2 SATCOM ⑤", "B3 CAN ⑧ (실데이터)",
          "+ A1①·A3②·B1⑧ (설계)"], "#eef2f7", "#34495e")
    _box(ax, 6.7, 3.6, 3.0, 2.4, "🧠 DNN 탐지기 + 규칙",
         ["1D-CNN (GNSS)", "Autoencoder (SATCOM)", "MLP (CAN)", "RAIM/화이트리스트"],
         "#e8f6ef", "#27ae60")
    _box(ax, 10.1, 3.6, 2.6, 2.4, "🔵 방어 에이전트",
         ["LLM(Claude) 두뇌", "위협분류·플레이북", "MITRE/SPARTA", "사고보고"], "#e8effd", "#2c6fd6")

    _arrow(ax, 2.9, 4.8, 3.3, 4.8)
    _arrow(ax, 6.3, 4.8, 6.7, 4.8)
    _arrow(ax, 9.7, 4.8, 10.1, 4.8)

    _box(ax, 1.8, 1.1, 9.4, 1.6, "Orchestrator",
         ["공격 → 탐지 → 대응 루프 · NIST CSF(탐지→대응→복구) 타임라인 · 지표(TPR/FPR/탐지지연)"],
         "#f7f3e8", "#b9770e")
    _arrow(ax, 3.0, 3.6, 4.0, 2.7)
    _arrow(ax, 11.0, 3.6, 9.5, 2.7)

    ax.text(6.5, 0.55, "DNN=감각(탐지) · LLM=두뇌(판단) · 규칙=설명가능 · "
            "키 없으면 규칙 폴백으로 오프라인 완주",
            ha="center", fontsize=9, style="italic", color="#555")
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-dir", default=None)
    args = ap.parse_args()
    docs_dir = resolve_docs_dir(args.docs_dir)
    fig = build()
    save_fig(fig, "overview", "architecture.png", docs_dir)
    # docs/ 에도 사본
    docs = os.path.join(REPO_ROOT, "docs")
    os.makedirs(docs, exist_ok=True)
    fig2 = build()
    fig2.savefig(os.path.join(docs, "architecture.png"), bbox_inches="tight")
    print("architecture.png 저장 완료")


if __name__ == "__main__":
    main()
