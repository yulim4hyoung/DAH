"""🔵 Detector 에이전트 — DNN 탐지기(도구)를 호출·해석해 경보 발령.

판정은 DNN+규칙(결정적), 자연어 위협분석은 LLM(있으면). 통합본 Part 6 대응.
"""
from __future__ import annotations
from .. import tools

_SYS = ("너는 무인체계(UAV/UGV) 통신보안 SOC의 위협분석 에이전트다. "
        "탐지기 출력과 근거를 받아, 위협을 2~3문장으로 간결하게 한국어로 분석하라. "
        "과장 없이 사실 기반으로, 왜 이 판정인지 근거를 들어 설명하라.")


class DetectorAgent:
    def __init__(self, llm=None):
        self.llm = llm

    def run(self, scn, bundle, atk):
        alert = tools.run_detector_tool(scn.KEY, bundle, atk)
        analysis = self._analyze(scn, alert)
        return alert, analysis

    def _analyze(self, scn, alert) -> str:
        reasons = " / ".join(alert["reasons"]) if alert["reasons"] else "규칙 임계 미도달(경보는 DNN 기반)"
        if self.llm and self.llm.available:
            ev = ", ".join(f"{k}={v}" for k, v in alert["evidence"].items())
            user = (f"시나리오: {scn.TITLE} (계층 {scn.LAYER})\n"
                    f"탐지기: {alert['detector']} / 공격확률·점수: {alert['score']}\n"
                    f"증거: {ev}\n규칙 근거: {reasons}")
            out = self.llm.complete(_SYS, user)
            if out:
                return out
        # 규칙 폴백 템플릿
        return (f"{scn.LAYER} 계층에서 {alert['detector']} 기반 이상 탐지(점수 {alert['score']}). "
                f"근거: {reasons}.")
