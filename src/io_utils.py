"""산출물 저장 유틸 — results/ 와 (있으면) dev_docu/ 에 지표·그림·로그·메타를 남긴다.

보고서 작성을 위해 각 시나리오 폴더에 다음을 남긴다:
  metrics.md (붙여넣기용 표) · *.png (300DPI) · run_log.txt · run_meta.json
"""
from __future__ import annotations
import os
import sys
import json
import random

# Windows 콘솔/파이프 한글·이모지 인코딩 보정
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import matplotlib
matplotlib.use("Agg")  # 비대화형(무인 실행)
import matplotlib.pyplot as plt

from matplotlib import font_manager
from rich.console import Console

from .paths import results_dir, DOCS_SUBDIR


def _setup_korean_font():
    """그림 한글 깨짐 방지 — 시스템 한글 폰트 우선 적용."""
    available = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Malgun Gothic", "NanumGothic", "NanumSquare", "AppleGothic", "Gulim"):
        if cand in available:
            plt.rcParams["font.family"] = cand
            return cand
    return None


_KFONT = _setup_korean_font()

# 보고서 그림 공통 스타일
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 300, "font.size": 11,
                     "axes.grid": True, "grid.alpha": 0.3, "axes.unicode_minus": False})


def new_console() -> Console:
    """녹화 가능한 콘솔(나중에 run_log.txt로 export). 레거시 Windows 렌더 비활성."""
    return Console(record=True, width=100, legacy_windows=False)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except Exception:
        pass


def _target_dirs(scenario_key: str, docs_dir: str | None) -> list[str]:
    """이 시나리오 산출물을 저장할 디렉터리 목록(results + docs)."""
    dirs = [os.path.join(results_dir(), scenario_key)]
    if docs_dir:
        sub = DOCS_SUBDIR.get(scenario_key, scenario_key)
        dirs.append(os.path.join(docs_dir, sub))
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    return dirs


def save_fig(fig, scenario_key: str, name: str, docs_dir: str | None) -> None:
    for d in _target_dirs(scenario_key, docs_dir):
        fig.savefig(os.path.join(d, name), bbox_inches="tight")
    plt.close(fig)


def save_json(scenario_key: str, name: str, obj: dict, docs_dir: str | None) -> None:
    for d in _target_dirs(scenario_key, docs_dir):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)


def save_text(scenario_key: str, name: str, text: str, docs_dir: str | None) -> None:
    for d in _target_dirs(scenario_key, docs_dir):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write(text)


def save_console_log(console: Console, scenario_key: str, name: str, docs_dir: str | None) -> None:
    text = console.export_text(clear=False)
    save_text(scenario_key, name, text, docs_dir)


def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def save_metrics_md(scenario_key: str, title: str, sections: list[tuple[str, str]],
                    docs_dir: str | None) -> None:
    """보고서 붙여넣기용 metrics.md 저장.
    sections = [(소제목, 마크다운본문), ...]
    """
    parts = [f"# {title}", ""]
    for heading, body in sections:
        if heading:
            parts.append(f"## {heading}")
        parts.append(body)
        parts.append("")
    save_text(scenario_key, "metrics.md", "\n".join(parts), docs_dir)
