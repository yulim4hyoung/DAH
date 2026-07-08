"""결계(結界) 데모 진입점 — 공격→탐지→대응 오케스트레이션을 실행.

사용:
  python src/run_demo.py --scenario all --docs-dir "…/dev_docu"
  python src/run_demo.py --scenario a2_gnss

먼저 `python src/train.py --scenario all` 로 탐지기를 학습해 두어야 한다.
LLM(Claude)은 ANTHROPIC_API_KEY가 있으면 자동 활성, 없으면 규칙 폴백.
"""
from __future__ import annotations
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.paths import load_config, models_dir, resolve_docs_dir
from src.io_utils import new_console, set_seed, save_text, save_console_log, md_table
from src.scenarios import registry
from src.agents.orchestrator import Orchestrator


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="all")
    ap.add_argument("--docs-dir", default=None)
    ap.add_argument("--evasive", action="store_true",
                    help="지원 시나리오(A2)에 회피형 공격 프로파일 사용 — "
                         "규칙 불발/경계신뢰도로 LLM 2차 소견 시연")
    args = ap.parse_args()

    cfg = load_config()
    set_seed(cfg["seed"])
    docs_dir = resolve_docs_dir(args.docs_dir)
    console = new_console()

    keys = registry.all_keys() if args.scenario == "all" else [args.scenario]

    # 모델 존재 확인
    missing = [k for k in keys if not os.path.exists(os.path.join(models_dir(), f"{k}.pt"))]
    if missing:
        console.print(f"[red]학습된 모델 없음: {missing}. 먼저 실행:[/] "
                      f"python src/train.py --scenario all")
        console.print(console.export_text())
        return

    orch = Orchestrator(cfg, console, evasive=args.evasive)
    results, reports = orch.run(keys)

    # 산출물 저장(demo)
    for key, md in reports.items():
        save_text("demo", f"incident_{key}.md", md, docs_dir)
    # 요약 타임라인
    rows = [[r["title"], r["layer"], r["threat"],
             "탐지" if r["detected"] else "정상", r["score"],
             (f"{r['latency']}{r['latency_unit']}" if r["latency"] is not None else "-")]
            for r in results]
    summary = ("# 결계(結界) 오케스트레이션 요약\n\n"
               f"LLM 상태: {orch.llm.status}\n\n"
               + md_table(["시나리오", "계층", "위협", "탐지", "점수", "탐지지연"], rows)
               + "\n\n> 각 시나리오 상세는 `incident_<key>.md` 참조. "
                 "콘솔 전체 흐름은 `orchestrator_timeline.txt`.")
    save_text("demo", "orchestrator_timeline_summary.md", summary, docs_dir)
    save_console_log(console, "demo", "orchestrator_timeline.txt", docs_dir)
    console.print(f"\n[green]데모 완료[/] · 산출물 저장: results/demo"
                  + (f" + dev_docu/demo" if docs_dir else ""))


if __name__ == "__main__":
    main()
