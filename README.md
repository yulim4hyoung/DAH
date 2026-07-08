# 결계(結界) — UAV/UGV 통신보안 멀티에이전트 방어 (DAH 2026)

> 통합본 서베이의 **6개 공격 시나리오를 관통하는 하나의 AI 방어 프레임워크**.
> 🔴공격 에이전트가 6단계 킬체인을 구동하면, 🧠**DNN 탐지기**(감각)가 이상을 잡고
> 🔵**LLM(Claude) 방어 에이전트**(두뇌)가 위협을 분류해 NIST CSF 플레이북으로 대응한다.

![architecture](docs/architecture.png)

## 1. 핵심 요약
- **DNN = 감각(탐지), LLM = 두뇌(판단)** — LLM 에이전트가 학습된 DNN 탐지기를 *도구(tool)*로 호출.
- **대표 3개 시나리오를 실행 가능하게 구현**(서로 다른 계층 + 실데이터 1건), 나머지 3개는 동일 프레임워크 확장으로 설계.
- **규칙(RAIM·화이트리스트) 병행** → 설명가능. **키 없으면 규칙 폴백**으로 오프라인 완주.

| 시나리오 | 계층 | 공격 | 탐지기 | 데이터 |
| --- | --- | --- | --- | --- |
| **A2** | ⑦ PNT | GNSS 스푸핑(점진 표류) | 1D-CNN(다특징 시계열) | 합성 |
| **B2** | ⑤ 위성 | SATCOM 관리망·모뎀 침해(AcidRain형) | 오토인코더(비지도) | 합성 |
| **B3** | ④⑧ 내부버스 | Wi-Fi→CAN 인젝션 | 경량 MLP | 합성(실 Car-Hacking 로더 포함) |
| (설계) | ①②⑧ | RC Takeover / MAVLink CVE / ROS2 | 스펙트로그램CNN·LSTM·GNN | — |

## 2. 빠른 시작
```powershell
# 가상환경 + 의존성 (Python 3.12)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# (선택) 실제 Claude 구동 — 없으면 규칙 폴백으로 동작
setx ANTHROPIC_API_KEY "sk-ant-..."      # 새 터미널에서 적용

# 1) 탐지기 학습 → 지표·그래프 생성
.\.venv\Scripts\python.exe src\train.py --scenario all

# 2) 공격→탐지→대응 데모
.\.venv\Scripts\python.exe src\run_demo.py --scenario all
```
> `--docs-dir "<경로>"` 를 주면 보고서용 근거자료(지표표·그림·사고보고)를 그 폴더에 추가 저장한다.

## 3. 대표 결과 (합성데이터 PoC · 시드 42)
| 시나리오 | 지표 |
| --- | --- |
| A2 GNSS | 정확도 0.98 · 공격탐지 AUC 0.99 · 스푸핑 탐지지연(중앙값) ~4초 |
| B2 SATCOM | 이상탐지 AUC 0.99 · F1 0.96 · 탐지지연 ~2버킷(모뎀 마비 전 조기 탐지) |
| B3 CAN | 정확도 ~0.99 · macro-F1 ~0.99 (CAN IDS 문헌값과 부합) |

> 값은 합성/통제 데이터 기준 PoC이며, 통합본이 인용한 문헌값(GNSS 스푸핑 F1≈0.97, CAN IDS F1≈0.99)과 정합. 실 데이터셋(TEXBAT/OAKBAT, Car-Hacking) 연동은 로더에 준비(향후과제).

## 4. 프로젝트 구조
```
dev/
├── README.md · requirements.txt · config.yaml · .env.example
├── src/
│   ├── train.py           # 탐지기 학습·평가(지표·그래프)
│   ├── run_demo.py        # 공격→탐지→대응 오케스트레이션 데모
│   ├── make_diagram.py    # 아키텍처 다이어그램 생성
│   ├── mapping.py         # MITRE/SPARTA/NIST CSF·플레이북
│   ├── sim/               # 합성 시뮬레이터(gnss·satcom·can)
│   ├── detect/            # DNN 탐지기 + 규칙 베이스라인
│   ├── scenarios/         # 시나리오 플러그인 + 레지스트리
│   └── agents/            # recon·attacker·detector·responder·orchestrator + LLM 래퍼
├── results/               # 코드 기본 출력(지표·그림·로그)
└── docs/                  # architecture.(md|png) · demo.md
```

## 5. 환경변수
| 변수 | 용도 |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude 구동(없으면 규칙 폴백). SDK가 자동 인식 |
| `GYEOLGYE_DOCS_DIR` | 보고서 근거자료 저장 폴더(`--docs-dir` 대체) |

## 6. 재현성 · 폴백
- 모든 난수는 `config.yaml`의 `seed`(기본 42)로 고정 → 결과 재현 가능.
- **LLM 키 없음** → 규칙 기반으로 완주 · **GPU 없음** → CPU(모델 작아 무방) · **실데이터 없음** → 합성.

## 7. ⚖️ 법적·윤리 고지
본 프로젝트의 모든 "공격"은 **합성 시뮬레이터/공개 데이터셋 내부에서만** 수행되며,
**실제 RF 송신·실장비 공격은 없다**(통합본 Part 4 법적 고지·차폐환경 연구 전제 준수).
방어 설계·탐지 연구 목적에 한정한다.

## 8. 보고서 연계 (DAH 예선)
- **§4 공격 시나리오** ← 킬체인 실행 + 통합본 6개 시나리오
- **§5 방어** ← DNN 탐지 지표(TPR/FPR/탐지지연) + NIST CSF 플레이북
- **§6 AI 에이전트** ← 본 프레임워크(다이어그램·에이전트 역할·프로토타입 결과)

## 9. 향후과제
실 데이터셋 연동(TEXBAT/OAKBAT·Car-Hacking), 설계 스텁 3종(RC①·MAVLink②·ROS2⑧) 구현,
LLM 에이전트의 tool-calling 정식화(Claude tool use), 온라인 스트리밍 탐지.
