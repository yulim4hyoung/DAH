"""프레임워크 매핑 — 위협 유형 ↔ MITRE ATT&CK / SPARTA, NIST CSF 대응 플레이북.

통합본 Part 3(공격 유형)·Part 5(방어)·Part 7(시나리오) 근거.
방어 에이전트(Responder)가 위협을 분류하고 플레이북을 선택할 때 참조한다.
"""
from __future__ import annotations

# 위협 유형 카탈로그 (탐지기 판정 → 위협 라벨)
THREATS = {
    "gnss_spoofing": {
        "name": "GNSS 스푸핑 (항법 무결성 공격)",
        "property": "무결성(Integrity) — '거짓말시키기'",
        "mitre": ["T0830 (AiTM)", "T0831 (Manipulation of Control)"],
        "sparta": ["EX-0014.04 (PNT Spoofing)"],
        "layer": "⑦ PNT",
    },
    "gnss_jamming": {
        "name": "GNSS 재밍 (항법 가용성 공격)",
        "property": "가용성(Availability) — '죽이기'",
        "mitre": ["T0814 (Denial of Service)"],
        "sparta": ["EX-0016.03 (PNT Jamming)"],
        "layer": "⑦ PNT",
    },
    "satcom_wiper": {
        "name": "SATCOM 관리망·모뎀 와이퍼 (BLOS C2 광역 마비)",
        "property": "가용성/무결성 — 관리평면 신뢰 악용",
        "mitre": ["T1495 (Firmware Corruption)", "T1561 (Disk Wipe)"],
        "sparta": ["EX-0010.02 (Wiper Malware)", "EX-0005 (Exploit HW/FW)"],
        "layer": "⑤ 위성(BLOS)",
    },
    "can_injection": {
        "name": "CAN 인젝션 (내부버스 구동계 변조)",
        "property": "무결성 — 무인증 버스 악용",
        "mitre": ["T0859 (Valid Accounts)", "T0814 (DoS)", "T1565 (Data Manipulation)"],
        "sparta": [],
        "layer": "⑧ 내부버스",
    },
    "nominal": {
        "name": "정상 (위협 없음)",
        "property": "-",
        "mitre": [], "sparta": [], "layer": "-",
    },
}

# NIST CSF 2.0 기반 대응 플레이북 (통합본 Part 5 §12·§13, Part 7 각 *-3)
PLAYBOOKS = {
    "gnss_spoofing": {
        "respond": [
            "GNSS 입력 차단 → INS 단독 추측항법(dead-reckoning) 전환",
            "페일세이프 진입: RTL(자동 귀환) 또는 Loiter(공중 대기)",
            "다중 별자리/주파수로 재획득 시도(GPS+Galileo+KPS)",
        ],
        "recover": [
            "비행로그 항법잔차·위성기하(DOP) 포렌식 → 표류 시작점 역추적",
            "스푸핑 구간 시그니처 추출 → 탐지모델 재학습",
        ],
        "protect": [
            "신호 인증: Galileo OSNMA / GPS Chimera / M-code",
            "CRPA 안테나 공간 널링 + GNSS·INS 강결합",
            "다중 별자리·다중 주파수 상시 수신",
        ],
    },
    "gnss_jamming": {
        "respond": [
            "재밍 대역 회피(주파수 hopping)·백업 링크 전환",
            "INS 단독 항법 + 페일세이프(RTL/Loiter)",
        ],
        "recover": ["재밍원 방향탐지·회피 경로 재계획", "RF 대역 정상화 확인 후 운용 재개"],
        "protect": ["CRPA 널링", "M-code/PRS 군용 신호", "관성항법 상시 융합"],
    },
    "satcom_wiper": {
        "respond": [
            "관리채널(NOC) 격리·차단 → 대량 펌웨어 푸시 중단",
            "감염 의심 모뎀 격리",
            "LOS RF/셀룰러로 멀티링크 절체 (BLOS 단일장애점 회피)",
        ],
        "recover": [
            "모뎀 펌웨어 포렌식·해시 무결성 재검증 후 재배포",
            "키 로테이션 + 관리망 접근 감사",
        ],
        "protect": [
            "관리망 망분리 + 강인증(MFA·제로트러스트)",
            "모뎀 Secure Boot·서명 펌웨어·롤백 보호",
            "공급망 무결성 검증 + 하드코딩 자격증명 제거",
        ],
    },
    "can_injection": {
        "respond": [
            "안전모드 진입 → 차량 정지(구동 토픽 차단)",
            "침해 세그먼트(도메인) 격리",
            "수동 통제로 전환",
        ],
        "recover": [
            "CAN 트레이스 포렌식 → 악성 ID·주입 프레임 식별",
            "ECU 펌웨어 무결성 검증 + 키 로테이션",
        ],
        "protect": [
            "CAN MAC(메시지 인증) 추가",
            "ID 화이트리스트·주기(period) 검사 상시",
            "구동계·센서 도메인 분리 + IDS 상주",
        ],
    },
}

# NIST CSF 단계 표기용
CSF_ORDER = ["respond", "recover", "protect"]
CSF_LABEL = {"respond": "대응(Respond)", "recover": "복구(Recover)", "protect": "예방·파훼(Protect)"}


def threat_info(threat_key: str) -> dict:
    return THREATS.get(threat_key, THREATS["nominal"])


def playbook(threat_key: str) -> dict:
    return PLAYBOOKS.get(threat_key, {})
