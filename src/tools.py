"""에이전트가 호출하는 도구(tool) 래퍼 — DNN 탐지기·시뮬레이터를 tool로 노출.

LLM 방어 에이전트는 신호를 직접 분류하지 않고 이 도구들을 호출해 판단한다.
"""
from __future__ import annotations
from .scenarios import registry


def load_detector_tool(scenario_key):
    """시나리오의 학습된 탐지기(DNN) 로드."""
    return registry.get(scenario_key).load()


def simulate_attack_tool(scenario_key, rng):
    """시나리오의 공격 시뮬레이션 실행 → 탐지기 입력 샘플 생성."""
    return registry.get(scenario_key).attack(rng)


def run_detector_tool(scenario_key, bundle, atk):
    """탐지기 추론 → 경보(alert) 반환."""
    return registry.get(scenario_key).detect(bundle, atk)
