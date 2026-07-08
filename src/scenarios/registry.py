"""시나리오 레지스트리 — 프레임워크가 커버하는 통합본 6개 시나리오.

구현 3개(A2·B2·B3)는 실행 가능한 플러그인, 나머지 3개(A1·A3·B1)는
'같은 프레임워크에 이렇게 꽂힌다'는 설계 스텁(문서/보고서용).
"""
from __future__ import annotations
from . import a2_gnss, b2_satcom, b3_can

# 실행 가능한 시나리오 (공격→탐지→대응)
IMPLEMENTED = {
    "a2_gnss": a2_gnss,
    "b2_satcom": b2_satcom,
    "b3_can": b3_can,
}

# 설계만(프레임워크 확장 지점) — 보고서 §4에서 서술, 코드 데모는 미구현
DESIGN_STUBS = {
    "a1_rc": {"title": "RC 링크 Takeover(FHSS)", "layer": "① RC", "threat": "rc_takeover",
              "detector": "RF 스펙트로그램 CNN + LSTM(도약 시퀀스)",
              "note": "탐지기만 교체하면 동일 프레임워크에 편입(김태형 담당)"},
    "a3_mavlink": {"title": "MAVLink 무인증 셸(CVE-2026-1579)", "layer": "② 텔레메트리",
                   "threat": "mavlink_injection", "detector": "시퀀스 LSTM(MUVIDS식)",
                   "note": "PX4 SITL 로그 → 시퀀스 탐지기로 확장(반현준 담당)"},
    "b1_ros2": {"title": "ROS2 SROS2 권한 취약점", "layer": "⑧ 미들웨어",
                "threat": "ros2_topic_spoof", "detector": "GNN/오토인코더(토픽 그래프)",
                "note": "DDS 토픽 그래프 → 이상 노드 탐지로 확장(반현준 담당)"},
}


def get(key):
    return IMPLEMENTED[key]


def all_keys():
    return list(IMPLEMENTED.keys())
