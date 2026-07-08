"""Orchestrator — 공격→탐지→대응 루프를 시나리오별로 실행하고 타임라인을 기록.

각 시나리오: Recon → Attacker(킬체인) → Detector(DNN+규칙) → Responder(플레이북).
결과를 rich 콘솔 타임라인 + 사고보고(md)로 남긴다(보고서 §6 근거).
"""
from __future__ import annotations
import numpy as np
from rich.panel import Panel
from rich.table import Table

from ..paths import load_config
from ..scenarios import registry
from .. import mapping
from .base import LLMClient
from .recon import ReconAgent
from .attacker import AttackerAgent
from .detector import DetectorAgent
from .responder import ResponderAgent


def _ts(step: int) -> str:
    s = step * 2
    return f"[t+00:{s:02d}]"


class Orchestrator:
    def __init__(self, cfg: dict, console):
        self.cfg = cfg
        self.console = console
        self.llm = LLMClient(cfg)
        self.recon = ReconAgent(self.llm)
        self.attacker = AttackerAgent()
        self.detector = DetectorAgent(self.llm)
        self.responder = ResponderAgent(self.llm)

    def run(self, scenario_keys):
        c = self.console
        c.rule("[bold]SENTINEL — 공격→탐지→대응 오케스트레이션")
        c.print(f"🧠 방어 에이전트 구동: [bold]{self.llm.status}[/]  "
                f"(DNN 탐지기는 항상 활성)")
        results = []
        reports = {}
        for key in scenario_keys:
            scn = registry.get(key)
            rng = np.random.default_rng(self.cfg["seed"] + sum(ord(ch) for ch in key))
            step = 0
            c.print()
            c.rule(f"[bold cyan]{scn.LAYER} · {scn.TITLE}")

            # 1) Recon
            c.print(f"{_ts(step)} 🔴 [bold]Recon[/] · {self.recon.run(scn)}"); step += 1

            # 2) Attacker — 6단계 킬체인
            c.print(f"{_ts(step)} 🔴 [bold]Attacker[/] · 6단계 킬체인 구동(시뮬레이션·오프라인)"); step += 1
            kc = Table(show_header=True, header_style="red", box=None, pad_edge=False)
            for col in ("단계", "행위", "도구"):
                kc.add_column(col)
            for s, act, tool in scn.KILLCHAIN:
                kc.add_row(s, act, tool)
            c.print(kc)
            atk = self.attacker.run(scn, rng)

            # 3) Detector — DNN 도구 호출
            alert, analysis = self.detector.run(scn, atk_load(scn), atk)
            lat = (f" · 탐지지연 {alert['latency']}{alert['latency_unit']}"
                   if alert.get("latency") is not None else "")
            c.print(f"{_ts(step)} 🧠 [bold]Detector[/] · {alert['detector']} 호출 → "
                    f"{'🚨 이상탐지' if alert['detected'] else '정상'} "
                    f"(점수 {alert['score']}{lat})"); step += 1
            ev = "  ".join(f"{k}={v}" for k, v in alert["evidence"].items())
            c.print(f"        증거: {ev}")
            for rsn in alert["reasons"]:
                c.print(f"        • {rsn}")
            c.print(Panel(analysis, title="🧠 위협 분석(에이전트)", border_style="cyan",
                          padding=(0, 1)))

            # 4) Responder — 플레이북
            dec = self.responder.run(scn, alert)
            info, pb = dec["threat_info"], dec["playbook"]
            c.print(f"{_ts(step)} 🔵 [bold]Responder[/] · 위협분류 → 플레이북 선택 "
                    f"(MITRE {', '.join(info['mitre']) or '-'} / "
                    f"SPARTA {', '.join(info['sparta']) or '-'})"); step += 1
            for phase in mapping.CSF_ORDER:
                if pb.get(phase):
                    c.print(f"        [{mapping.CSF_LABEL[phase]}]")
                    for a in pb[phase]:
                        c.print(f"          - {a}")
            c.print(Panel(dec["summary"], title="🔵 지휘 요약(에이전트)", border_style="blue",
                          padding=(0, 1)))

            results.append({"key": key, "title": scn.TITLE, "layer": scn.LAYER,
                            "threat": info["name"], "detected": alert["detected"],
                            "score": alert["score"], "latency": alert.get("latency"),
                            "latency_unit": alert.get("latency_unit", "")})
            reports[key] = _incident_md(scn, alert, dec, analysis)

        # 요약표
        c.print()
        c.rule("[bold]오케스트레이션 요약")
        t = Table(show_header=True, header_style="bold")
        for col in ("시나리오", "계층", "위협", "탐지", "점수", "탐지지연"):
            t.add_column(col)
        for r in results:
            lats = (f"{r['latency']}{r['latency_unit']}" if r["latency"] is not None else "-")
            t.add_row(r["title"][:22], r["layer"], r["threat"][:18],
                      "🚨" if r["detected"] else "정상", str(r["score"]), lats)
        c.print(t)
        # 설계 스텁 안내
        stub = ", ".join(v["title"] for v in registry.DESIGN_STUBS.values())
        c.print(f"[dim]※ 프레임워크 확장(설계): {stub}[/]")
        return results, reports


# 탐지기 로드 캐시(시나리오당 1회)
_CACHE = {}


def atk_load(scn):
    if scn.KEY not in _CACHE:
        _CACHE[scn.KEY] = scn.load()
    return _CACHE[scn.KEY]


def _incident_md(scn, alert, dec, analysis) -> str:
    info, pb = dec["threat_info"], dec["playbook"]
    ev = "\n".join(f"| {k} | {v} |" for k, v in alert["evidence"].items())
    reasons = "\n".join(f"- {r}" for r in alert["reasons"]) or "- (DNN 기반 탐지)"
    def block(phase):
        return "\n".join(f"- {a}" for a in pb.get(phase, []))
    lat = (f"{alert['latency']}{alert['latency_unit']}" if alert.get("latency") is not None else "-")
    return f"""# 사고보고 — {scn.TITLE}

- **시나리오**: `{scn.KEY}` · 계층 {scn.LAYER}
- **위협**: {info['name']} ({info['property']})
- **프레임워크 매핑**: MITRE {', '.join(info['mitre']) or '-'} / SPARTA {', '.join(info['sparta']) or '-'}
- **탐지기**: {alert['detector']} · 점수 {alert['score']} · 탐지지연 {lat}

## 증거
| 지표 | 값 |
| --- | --- |
{ev}

## 규칙 근거(설명가능)
{reasons}

## 위협 분석(에이전트)
{analysis}

## 대응 플레이북 (NIST CSF)
### 대응(Respond)
{block('respond')}
### 복구(Recover)
{block('recover')}
### 예방·파훼(Protect)
{block('protect')}

## 지휘 요약(에이전트)
{dec['summary']}
"""
