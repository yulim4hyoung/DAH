"""🔴 Attacker 에이전트 — 6단계 킬체인 구동(전부 시뮬레이션·오프라인).

실제 RF 송신·실장비 공격 없음. 합성 시뮬레이터/공개 데이터셋 내부에서만 동작.
"""
from __future__ import annotations
from .. import tools


class AttackerAgent:
    def run(self, scn, rng, evasive=False):
        """시나리오의 공격을 시뮬레이션하고 킬체인·산출 샘플을 반환.

        evasive=True면 지원 시나리오(현재 A2)가 회피형(느린 표류) 공격 프로파일을 쓴다.
        """
        atk = tools.simulate_attack_tool(scn.KEY, rng, evasive)
        return atk

    def killchain(self, scn):
        return scn.KILLCHAIN
