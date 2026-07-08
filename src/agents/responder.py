"""🔵 Responder 에이전트 — 위협 분류→플레이북 선택→사고보고(NIST CSF).

위협 유형을 MITRE/SPARTA에 매핑하고 통합본 Part 5 대응 플레이북을 선택한다.
"""
from __future__ import annotations
from .. import mapping

_SYS = ("너는 무인체계 통신보안 대응(Response) 지휘 에이전트다. "
        "탐지된 위협과 선택된 대응 플레이북을 받아, 지휘관에게 보고할 3~4문장 요약을 "
        "한국어로 작성하라. 즉시조치→복구→근본대응 순서와 우선순위를 명확히 하라.")


class ResponderAgent:
    def __init__(self, llm=None):
        self.llm = llm

    def run(self, scn, alert) -> dict:
        threat = alert["threat"]
        info = mapping.threat_info(threat)
        pb = mapping.playbook(threat)
        summary = self._summary(scn, alert, info, pb)
        return {"threat_info": info, "playbook": pb, "summary": summary}

    def _summary(self, scn, alert, info, pb) -> str:
        if self.llm and self.llm.available and pb:
            steps = "; ".join(pb.get("respond", [])[:2])
            user = (f"위협: {info['name']} ({info['property']})\n"
                    f"계층: {scn.LAYER} / MITRE: {', '.join(info['mitre']) or '-'} / "
                    f"SPARTA: {', '.join(info['sparta']) or '-'}\n"
                    f"즉시조치 후보: {steps}")
            out = self.llm.complete(_SYS, user)
            if out:
                return out
        if not pb:
            return "위협 미확정 — 정상 범위로 판단, 상시 모니터링 유지."
        return (f"'{info['name']}' 확정. 즉시조치: {pb['respond'][0]}. "
                f"이후 복구·근본대응(예방)까지 단계 실행. MITRE {', '.join(info['mitre']) or '-'}.")
