"""🔵 Responder 에이전트 — 위협 분류→플레이북 선택→사고보고(NIST CSF).

위협 유형을 MITRE/SPARTA에 매핑하고 통합본 Part 5 대응 플레이북을 선택한다.
"""
from __future__ import annotations
from .. import mapping

_SYS = ("너는 무인체계 통신보안 대응(Response) 지휘 에이전트다. "
        "탐지된 위협과 선택된 대응 플레이북을 받아, 지휘관에게 보고할 3~4문장 요약을 "
        "한국어로 작성하라. 즉시조치→복구→근본대응 순서와 우선순위를 명확히 하라. "
        "특히 가용성(SLA)을 고려해, 신뢰도가 낮으면 서비스를 유지하는 완화(graceful)를, "
        "높으면 강제 차단(aggressive)을 택한 이유를 한 문장으로 밝혀라.")

_TIER_KO = {"graceful": "완화(서비스 유지)", "aggressive": "강제 차단", "none": "-"}
_TIER_NOTE = {
    "graceful": "SLA 보호: 탐지 신뢰도가 낮아 서비스를 유지하는 완화형 대응을 선택",
    "aggressive": "탐지 신뢰도가 높아 가용성 희생을 감수한 강제 차단을 선택",
    "none": "정상 범위 — 상시 모니터링 유지",
}


class ResponderAgent:
    def __init__(self, llm=None):
        self.llm = llm

    def run(self, scn, alert) -> dict:
        threat = alert["threat"]
        info = mapping.threat_info(threat)
        # 신뢰도(0~1): 탐지된 경우에만 유효. score 폴백은 [0,1]로 클리핑.
        conf = alert.get("confidence", alert.get("score"))
        conf = (max(0.0, min(1.0, float(conf)))
                if (conf is not None and alert.get("detected")) else None)
        pb, tier = mapping.playbook_with_tier(threat, conf)
        summary = self._summary(scn, alert, info, pb, tier, conf)
        return {"threat_info": info, "playbook": pb, "summary": summary,
                "tier": tier, "confidence": conf}

    def _summary(self, scn, alert, info, pb, tier="none", conf=None) -> str:
        if self.llm and self.llm.available and pb:
            steps = "; ".join(pb.get("respond", [])[:2])
            user = (f"위협: {info['name']} ({info['property']})\n"
                    f"계층: {scn.LAYER} / MITRE: {', '.join(info['mitre']) or '-'} / "
                    f"SPARTA: {', '.join(info['sparta']) or '-'}\n"
                    f"탐지 신뢰도: {conf if conf is not None else '-'} → 대응강도: {_TIER_KO[tier]}\n"
                    f"즉시조치 후보: {steps}")
            out = self.llm.complete(_SYS, user)
            if out:
                return out
        if not pb:
            return "위협 미확정 — 정상 범위로 판단, 상시 모니터링 유지."
        return (f"'{info['name']}' 확정. {_TIER_NOTE[tier]}. 즉시조치: {pb['respond'][0]}. "
                f"이후 복구·근본대응(예방)까지 단계 실행. MITRE {', '.join(info['mitre']) or '-'}.")
