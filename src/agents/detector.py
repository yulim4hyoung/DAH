"""🔵 Detector 에이전트 — DNN 탐지기(도구)를 호출·해석해 경보 발령.

판정은 DNN+규칙(결정적), 자연어 위협분석은 LLM(있으면). 통합본 Part 6 대응.

애매한 경보(DNN-규칙 불일치, 또는 신뢰도 경계구간)에서는 LLM이 '2차 소견(자문)'을
추가로 낸다. 이 소견은 threat·score·tier 등 어떤 결정적 값도 바꾸지 않는다 —
지표 재현성을 지키면서, 사람이 판단하기 애매한 경우에 LLM이 실제로 의견을 보태는
지점을 만든 것(축③).
"""
from __future__ import annotations
from .. import mapping
from .. import tools

_SYS = ("너는 무인체계(UAV/UGV) 통신보안 SOC의 위협분석 에이전트다. "
        "탐지기 출력과 근거를 받아, 위협을 2~3문장으로 간결하게 한국어로 분석하라. "
        "과장 없이 사실 기반으로, 왜 이 판정인지 근거를 들어 설명하라.")

_SYS_ADJ = ("너는 SOC의 2차 검토(자문) 에이전트다. 자동 판정 시스템이 이미 확정한 결과를 "
            "바꿀 권한은 없다 — 오직 참고 의견만 제시한다. DNN 탐지기와 설명가능 규칙이 "
            "불일치하거나 신뢰도가 애매한 경계 사례를 받아, (1) 실제 공격일 가능성이 높은지 "
            "오탐일 가능성이 높은지, (2) 그 근거, (3) 권고 태세(예: 관찰 강화/즉시 확전 등)를 "
            "2~3문장으로 간결하게 한국어로 제시하라.")

LOW_CONFIDENCE = 0.5  # HIGH_CONFIDENCE(0.7)와 짝을 이루는 하한 — [0.5,0.7) 구간을 '경계'로 본다


class DetectorAgent:
    def __init__(self, llm=None):
        self.llm = llm

    def run(self, scn, bundle, atk):
        # 판정·지표는 결정적으로 여기서 계산(재현성). LLM은 서술 + (애매할 때만) 2차 소견.
        alert = tools.run_detector_tool(scn.KEY, bundle, atk)
        analysis = self._analyze(scn, alert)
        ambiguous, why = self._is_ambiguous(alert)
        alert["ambiguous"] = ambiguous
        alert["second_opinion"] = self._second_opinion(scn, alert, why) if ambiguous else None
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

    def _is_ambiguous(self, alert) -> tuple[bool, str]:
        """DNN-규칙 불일치 또는 신뢰도 경계구간이면 (True, 사유). 아니면 (False, "")."""
        if not alert.get("detected"):
            return (False, "")
        if not alert.get("reasons"):
            return (True, "DNN은 이상탐지했으나 설명가능 규칙이 근거를 내지 못함(불일치)")
        conf = alert.get("confidence")
        if conf is not None and LOW_CONFIDENCE <= conf < mapping.HIGH_CONFIDENCE:
            return (True, f"탐지 신뢰도 {conf:.2f}가 경계구간[{LOW_CONFIDENCE},{mapping.HIGH_CONFIDENCE}) 내")
        return (False, "")

    def _second_opinion(self, scn, alert, why: str) -> str:
        if self.llm and self.llm.available:
            reasons = " / ".join(alert["reasons"]) if alert["reasons"] else "(근거 없음)"
            ev = ", ".join(f"{k}={v}" for k, v in alert["evidence"].items())
            user = (f"시나리오: {scn.TITLE} (계층 {scn.LAYER})\n"
                    f"애매함 사유: {why}\n"
                    f"탐지기: {alert['detector']} / 점수(신뢰도): {alert['score']}\n"
                    f"증거: {ev}\n규칙 근거: {reasons}")
            out = self.llm.complete(_SYS_ADJ, user)
            if out:
                return out
        return (f"⚠️ {why}. 자동판정({alert['threat']})은 유지하되, "
                f"수동·LLM 재검토를 권장한다.")
