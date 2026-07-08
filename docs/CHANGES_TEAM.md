# 브랜치 변경내역 — 반현준 작업분 전체 설명 (팀 공유용)

> 원본 프로젝트("결계")는 **형유림**님이 만들었습니다. 이 문서는 **반현준**이 브랜치
> `feat/sla-second-opinion`에서 원본 위에 추가·수정한 내용을 정리한 것입니다.
> 원본의 동작(재현성·API 키 없이도 완주하는 폴백 구조)은 그대로 보존했습니다 — 판정 로직(위협 분류·지표)은 바뀌지 않았습니다.

## 목차

1. [30초 요약](#1-30초-요약)
2. [왜 손댔는가 — 심사자 관점에서 본 약점 3가지](#2-왜-손댔는가--심사자-관점에서-본-약점-3가지)
3. [축① SLA(가용성) 인지 대응](#3-축①-sla가용성-인지-대응)
4. [축② 적응형 공격 강건성](#4-축②-적응형-공격-강건성)
5. [축③ LLM 2차 소견 (tool_use 시도 → 롤백 → 재설계)](#5-축③-llm-2차-소견-tool_use-시도--롤백--재설계)
6. [전체 변경 파일 인벤토리](#6-전체-변경-파일-인벤토리)
7. [직접 돌려보는 법](#7-직접-돌려보는-법)
8. [정직한 한계 3가지](#8-정직한-한계-3가지)
9. [발표 말하기 포인트](#9-발표-말하기-포인트)
10. [안 건드린 것·제약](#10-안-건드린-것제약)
11. [README 문구 정정 기록](#11-readme-문구-정정-기록)

---

## 1. 30초 요약

| 축            | 한 줄 요약                                                                                                                | 배점 연결                       |
| ------------ | --------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| ① SLA 인지 대응  | 탐지 신뢰도에 따라 "서비스 유지 완화" vs "강제 차단" 2단계로 대응 강도를 나눴습니다                                                                   | ② 방어전략(25점)                 |
| ② 적응형 공격 강건성 | 탐지기가 배우지 않은 회피형 공격을 던져 성능 하락을 실측하고, 재학습으로 회복시켰습니다                                                                     | ① 공격시나리오(30) + ③ AI에이전트(25) |
| ③ LLM 2차 소견  | 처음엔 "LLM이 도구를 직접 호출"(tool_use)하는 방식으로 만들었다가, 판정에 영향을 주지 못해 **롤백**했습니다. 이후 "애매한 경보에서만 LLM이 실제 자문 의견을 내는" 구조로 다시 설계했습니다 | ③ AI에이전트(25)                |

세 축 모두 **판정·지표(정확도·F1·AUC 등)는 원본 그대로 재현**됩니다 — 형유림님이 만든 탐지기·규칙·학습 로직은 건드리지 않았고, 그 위에 "대응 방식"과 "설명 레이어"만 얹었습니다.

---

## 2. 왜 손댔는가 — 심사자 관점에서 본 약점 3가지

DAH 2026 배점은 공격시나리오30 / 방어25 / AI에이전트25 / 팀10 / 문서10입니다. 원본은 완성도가 높지만, 코드를 직접 뜯어보는 심사자 입장에서는 다음 세 가지가 약점으로 보일 수 있습니다.

1. **순환 평가** — 공격 시뮬레이터와 탐지기를 같은 팀이 만들고, 같은 시뮬레이터로 학습·평가합니다. "내가 낸 문제를 내가 푸는" 구조라 AUC 0.99 같은 숫자의 외적 타당성이 약할 수 있습니다. → **축②**로 보완했습니다.
2. **SLA(가용성) 개념 부재** — 대회의 핵심 채점축(본선 기준)인데, 원본 대응 매뉴얼은 탐지되면 무조건 "차량 정지·GPS 차단" 같은 강한 조치만 나갔습니다. 오탐이 났을 때 우리 스스로 서비스를 끊어버리는 구조였습니다. → **축①**로 보완했습니다.
3. **LLM이 장식적으로만 쓰임** — "LLM이 DNN을 tool로 호출해 위협을 분류한다"는 문구가 README에 있었지만, 실제로는 위협 분류가 100% 규칙/DNN 임계값(if문)으로 결정되고 LLM은 이미 정해진 결과를 문장으로 다듬기만 했습니다. → **축③**으로 보완했습니다(다만 처음엔 접근이 잘못됐다가 재설계한 과정이 있어 5장에 그대로 남겨뒀습니다).

---

## 3. 축① SLA(가용성) 인지 대응

### 무엇을, 왜 바꿨는가

원본은 위협이 탐지되면 신뢰도(점수가 0.51이든 0.99든)와 무관하게 **항상 같은 강도의 대응**만 나갔습니다. 오탐이 났을 때 서비스를 스스로 끊어버리는 자해성 리스크가 있고, 대회의 SLA(시스템 가용성 유지) 채점축을 전혀 반영하지 못하는 구조였습니다.

그래서 **탐지 신뢰도에 따라 대응 강도를 2단계로 나눴습니다**:

- **graceful(완화)**: 신뢰도가 낮을 때(0.7 미만) — 서비스를 유지하며 최소한으로만 개입합니다.
- **aggressive(강제 차단)**: 신뢰도가 높을 때(0.7 이상) — 기존처럼 강하게 차단합니다.

### 파일별 변경 내용

**`src/mapping.py`** — 핵심 신규 로직은 대부분 이 파일에 있습니다(파일 끝에 약 90줄 추가):

```python
RESPONSE_TIERS = {
    "gnss_spoofing": {
        "graceful": [
            "GNSS 신뢰가중치 하향 + INS 강결합 유지 → 임무 계속(비행 지속)",
            "다중 별자리·주파수 교차검증으로 이상 위성만 배제",
            ...
        ],
        "aggressive": [  # 원본 PLAYBOOKS와 동일 내용
            "GNSS 입력 차단 → INS 단독 추측항법(dead-reckoning) 전환", ...
        ],
    },
    # gnss_jamming, satcom_wiper, can_injection 도 같은 구조입니다
}

DISRUPTION_WEIGHT = {"none": 0.0, "graceful": 0.2, "aggressive": 1.0}
HIGH_CONFIDENCE = 0.7  # 이 값 이상이면 aggressive

def response_tier(threat_key, confidence, high_conf=HIGH_CONFIDENCE):
    tier = "aggressive" if confidence >= high_conf else "graceful"
    return (tier, RESPONSE_TIERS[threat_key][tier])

def playbook_with_tier(threat_key, confidence, high_conf=HIGH_CONFIDENCE):
    """respond만 tier로 교체하고, recover/protect는 공통으로 유지합니다."""
    pb = playbook(threat_key)
    tier, respond_actions = response_tier(threat_key, confidence, high_conf)
    merged = dict(pb); merged["respond"] = respond_actions
    return (merged, tier)
```

**`src/agents/responder.py`** — 신뢰도를 계산해 tier를 고르는 지점입니다:

```python
conf = alert.get("confidence", alert.get("score"))
conf = max(0.0, min(1.0, float(conf))) if (conf is not None and alert.get("detected")) else None
pb, tier = mapping.playbook_with_tier(threat, conf)
```

LLM 시스템 프롬프트에도 "신뢰도가 낮으면 완화를, 높으면 강제 차단을 택한 이유를 밝혀라"라는 지시를 추가했습니다.

**`src/scenarios/{a2_gnss,b2_satcom,b3_can}.py`** `detect()` — 각 탐지기가 `confidence`(0~1) 필드를 추가로 반환하도록 수정했습니다. GNSS/CAN은 소프트맥스 확률, SATCOM(오토인코더)은 재구성오차/임계값을 0~1로 정규화한 값입니다.

**`src/agents/orchestrator.py`** — 콘솔과 사고보고서에 `SLA 대응강도: 🟢 완화 / 🔴 강제차단 (신뢰도 X.XX)` 표시를 추가했습니다.

**`src/train.py`** — SLA 트레이드오프를 정량화하는 함수 3개를 새로 추가했습니다(파일 상단 헬퍼 구역):

```python
def sla_sweep(conf_all, y_all, high_conf, thresholds):
    """탐지 임계별로 '서비스 방해율'을 계산 — 일괄차단 정책 vs 신뢰도게이팅 정책 비교."""
    # 일괄차단: 경보가 뜨면 무조건 aggressive 취급 → 경보율 × 1.0
    # 게이팅:   신뢰도<high 인 경보만 graceful(가중치 0.2), 나머지는 aggressive
    ...
def plot_sla_tradeoff(rows, high_conf, title): ...  # 그래프
def sla_table(rows, picks=(0.5, 0.7, 0.9)): ...      # metrics.md용 표
```

이 함수들을 `train_gnss`/`train_satcom`/`train_can` 세 함수에 각각 연결해, 시나리오마다 `results/<key>/sla_tradeoff.png`와 metrics.md에 SLA 표를 자동 생성하게 했습니다.

**`src/make_report.py`** — 대시보드 `CHARTS` 딕셔너리에 `sla_tradeoff.png` 항목을 3개 시나리오 모두 추가했습니다.

### 실제 출력 예시

데모 콘솔·사고보고서에는 이렇게 표시됩니다(`results/demo/orchestrator_timeline.txt`, A2 예시):

```
 🔵 Responder · 위협분류 → 플레이북 선택 (MITRE T0830 (AiTM), T0831 (Manipulation of Control) / …)
        SLA 대응강도: 🔴 강제 차단 (탐지 신뢰도 0.81)
```

신뢰도가 0.7 미만이면(예: `--evasive` A2, 신뢰도 0.52) `🟢 완화(서비스 유지)`로 바뀝니다.

`metrics.md`에는 임계별 트레이드오프 표가 자동으로 붙습니다(`results/a2_gnss/metrics.md`):
| 임계 | 공격탐지율 | 경보율 | 서비스방해(일괄차단) | 서비스방해(게이팅) |
| --- | --- | --- | --- | --- |
| 0.50 | 0.948 | 0.382 | 0.382 | 0.381 |
| 0.70 | 0.947 | 0.381 | 0.381 | 0.381 |
| 0.90 | 0.942 | 0.378 | 0.378 | 0.378 |

### 한계 (실측 결과)

정책은 3개 시나리오 모두 구현했지만, 실제로 측정해보니 **원본 DNN들이 워낙 확신에 차 있어서**(경보의 99%가 신뢰도 0.9 이상) "애매한 경우"가 거의 발생하지 않습니다. 그래서 이 합성데이터에서는 게이팅의 수치적 이득이 작습니다(예: GNSS 서비스방해율 aggressive 0.382 vs gated 0.381). 정책은 옳지만, 이득은 탐지가 덜 확실한 실환경에서 더 커질 것으로 봅니다.

---

## 4. 축② 적응형 공격 강건성

### 무엇을, 왜 바꿨는가

"순환 평가" 비판을 정면으로 반박하려면, 탐지기가 **자기가 훈련받지 않은 공격**에도 대응할 수 있는지를 실험으로 보여줄 필요가 있었습니다. 그래서 GNSS 스푸핑에 **회피형(더 느리고 은밀한) 공격 프로파일**을 만들어 baseline 탐지기에 던지고, 성능이 떨어지는 것을 정직하게 보인 다음, **그 프로파일을 학습에 섞어 재훈련(hardening)**해서 회복시켰습니다.

### 파일별 변경 내용

**`src/sim/gnss_sim.py`** — 스푸핑 파라미터를 하드코딩에서 프로파일 딕셔너리로 분리했습니다:

```python
SPOOF_PROFILES = {
    "trained":    {"ramp": 25.0, "slope": 0.45, ...},  # 원본과 100% 동일한 값
    "slow_creep": {"ramp": 80.0, "slope": 0.07, ...},  # 회피형(느린 표류)
    "aggressive": {"ramp": 12.0, "slope": 0.9,  ...},  # 빠른 표류(탐지가 쉬움)
}

def generate_flight(kind, epochs, rng, window=20, profile=None):
    """profile=None이면 기존과 난수 스트림까지 완전히 동일합니다(회귀 없음)."""
    p = _resolve_profile(profile)  # None → "trained"
    ...
```

`generate_dataset()`에도 `spoof_profiles=` 인자를 추가해 여러 프로파일을 섞어 학습셋을 만들 수 있도록 확장했습니다(기본값을 안 주면 원본과 동일하게 동작합니다).

**`src/detect/rules.py`** `gnss_rule()` — 회피형 공격은 순간 잔차값이 임계(15m) 아래라 규칙이 못 잡는데, "최근 잔차가 완만하게 계속 오르는 추세"를 새 근거로 추가했습니다:

```python
def gnss_rule(feat_row, residual_trend=None):  # 기본값 None이면 기존과 동일하게 동작
    ...
    if residual_trend is not None and res <= 15 and residual_trend > 0.1:
        r.append(f"INS 잔차 완만한 상승추세 {residual_trend:.2f} m/s — 은밀 누적 표류(회피형 스푸핑) 정황")
```

**`src/scenarios/a2_gnss.py`** `detect()` — 최근 20개 에폭의 잔차로 선형회귀 기울기를 구해 위 규칙에 전달합니다.

**`src/train.py`** — `--adaptive-train` 플래그와 `train_gnss_hardened()` 함수를 새로 추가했습니다:

```python
def train_gnss_hardened(cfg, console):
    """trained+slow_creep+aggressive 프로파일을 섞어 재학습 → 별도 파일로 저장합니다."""
    profiles = ["trained", "slow_creep", "aggressive"]
    X, y, meta = generate_dataset(cfg, rng, spoof_profiles=profiles)
    model, scaler, hist = M.train_model(...)
    torch.save({...}, "models/a2_gnss_hardened.pt")  # baseline(a2_gnss.pt)은 건드리지 않습니다
```

**`src/eval_adaptive.py`** (완전 신규 파일) — baseline과 hardened 모델을 프로파일별로 비교 평가합니다:

```python
EARLY_DEADLINE = 10  # 공격개시 10초 이내 탐지 = "조기탐지"

def _eval(bundle, flights, W):
    """반환값: (조기탐지율, 전체탐지율, 중앙값지연). '전체탐지율'은 대개 100%라 의미가 약해서,
    운영상 핵심 지표는 '조기탐지율'로 잡았습니다 — 스푸핑은 늦게 잡으면 이미 항로가 끌려간 뒤라 소용없기 때문입니다."""
```

결과는 `results/a2_gnss/adaptive_robustness.{png,md}`로 저장됩니다.

### 실제 출력 예시

`results/a2_gnss/adaptive_robustness.md`에 저장되는 표입니다(`eval_adaptive.py` 실행 결과):
| 프로파일 | baseline 조기탐지 | hardened 조기탐지 | baseline 지연(s) | hardened 지연(s) |
| --- | --- | --- | --- | --- |
| 학습됨(기본) | 1.00 | 1.00 | 4 | 4 |
| 회피형(느린표류) | **0.59** | **0.90** | 8 | 5 |
| 공격적(빠른표류) | 1.00 | 1.00 | 3 | 3 |
그림 버전은 `adaptive_robustness.png`입니다(막대그래프, baseline 급락과 hardened 회복이 나란히 보입니다).

### 실측 결과

회피형(slow_creep) 공격에서 **baseline 조기탐지율이 0.90에서 0.59로 급락**합니다(지연도 4초에서 8초로 악화). 재학습(hardened) 후에는 **0.90으로 회복**합니다(지연 5초). 학습 밖 공격엔 약해질 수 있다는 것과, 재학습으로 회복 가능하다는 것을 그래프 한 장(`adaptive_robustness.png`)에 함께 보여줍니다.

### 회귀 없음 (검증 완료)

`profile=None`(기본값)일 때 원본 `gnss_sim.py`가 만드는 데이터와 **바이트 단위로 완전히 동일**함을 해시 비교로 확인했습니다. 즉 이 축을 추가해도 기존 A2/B2/B3 지표는 하나도 바뀌지 않습니다.

---

## 5. 축③ LLM 2차 소견 (tool_use 시도 → 롤백 → 재설계)

이 축은 **한 번 잘못 만들었다가 검토 과정에서 다시 설계한** 케이스라, 그 과정을 그대로 남겨두었습니다.

### 1차 시도: "LLM이 도구를 직접 호출한다" (tool_use) — 롤백함

원본 README에는 "LLM이 DNN 탐지기를 도구로 호출한다"고 적혀 있었지만 실제로는 그런 코드가 없었습니다. 그래서 처음엔 Anthropic API의 진짜 tool_use 기능을 사용해서, LLM이 실제로 `run_detector`라는 도구를 호출하고 그 결과를 받아 분석문을 쓰도록 만들었습니다(`src/agents/base.py`의 `run_with_tools()`, `src/tools.py`의 `DETECTOR_TOOL_SCHEMA` 등).

**하지만 검토 결과 문제가 있었습니다.** 이 도구 호출은 **위협 분류·점수·대응 등 어떤 결정에도 영향을 주지 않았습니다.** 도구가 반환하는 값은 이미 계산이 끝난 결정적 결과였고, LLM은 그걸 받아 문장만 썼습니다. 즉 "LLM이 tool을 쓴다"는 형식만 갖췄을 뿐, **탐지 성능이나 판단 품질을 실질적으로 높이지 못하는** 장식에 가까웠습니다. "판정을 전혀 바꾸지 않는 도구 호출이 소스 품질을 실제로 높이는가?"라는 질문에 "아니다"라고 답할 수밖에 없어서, **관련 코드를 전부 롤백**했습니다.

### 2차 설계: "애매할 때만 LLM이 실제 자문을 낸다" — 현재 구현

위협 분류는 여전히 결정적(규칙+DNN)으로 유지하되, **DNN과 규칙의 판단이 서로 다르거나(불일치), 신뢰도가 애매한 경계구간일 때만** LLM이 "이게 진짜 공격 같은지, 오탐 같은지"에 대한 **참고 의견**을 냅니다. 이 의견은 최종 판정·지표를 **절대 바꾸지 않습니다** — 순수하게 자문 역할만 합니다.

**`src/agents/detector.py`** — 핵심 로직을 새로 추가했습니다:

```python
LOW_CONFIDENCE = 0.5  # mapping.HIGH_CONFIDENCE(0.7)와 짝을 이뤄 [0.5, 0.7) 구간을 '경계'로 봅니다

def _is_ambiguous(self, alert) -> tuple[bool, str]:
    """DNN-규칙 불일치, 또는 신뢰도가 경계구간이면 (True, 사유)를 반환합니다."""
    if not alert.get("detected"):
        return (False, "")
    if not alert.get("reasons"):  # DNN은 탐지했는데 규칙이 근거를 못 낸 경우
        return (True, "DNN은 이상탐지했으나 설명가능 규칙이 근거를 내지 못함(불일치)")
    conf = alert.get("confidence")
    if conf is not None and LOW_CONFIDENCE <= conf < mapping.HIGH_CONFIDENCE:
        return (True, f"탐지 신뢰도 {conf:.2f}가 경계구간 내")
    return (False, "")

def _second_opinion(self, scn, alert, why) -> str:
    if self.llm and self.llm.available:
        out = self.llm.complete(_SYS_ADJ, user)  # 자문 전용 시스템 프롬프트
        if out: return out
    return f"⚠️ {why}. 자동판정({alert['threat']})은 유지하되, 수동·LLM 재검토를 권장한다."

def run(self, scn, bundle, atk):
    alert = tools.run_detector_tool(scn.KEY, bundle, atk)  # 결정적 판정(불변)
    analysis = self._analyze(scn, alert)                    # 원본과 동일한 서술
    ambiguous, why = self._is_ambiguous(alert)
    alert["second_opinion"] = self._second_opinion(scn, alert, why) if ambiguous else None
    return alert, analysis
```

**`src/agents/orchestrator.py`** — 애매한 경우 콘솔에 `🤖 LLM 2차 소견(자문)` 패널을 표시하고, `_incident_md()`에도 별도 섹션을 추가했습니다. `self.evasive` 플래그도 여기서 관리합니다.

**`--evasive` 시연 경로** (4개 파일을 거칩니다): `run_demo.py`의 `--evasive` 인자 → `Orchestrator(evasive=)` → `AttackerAgent.run(evasive=)` → `tools.simulate_attack_tool(evasive=)` → 시나리오의 `attack(evasive=)`. A2만 실제로 `profile="slow_creep"`을 사용합니다(B2/B3는 인자만 받고 무시하도록 해 하위호환을 유지했습니다).

### 실제 출력 예시

애매한 경우엔 콘솔·사고보고서에 노란 패널이 뜹니다(`results/demo/orchestrator_timeline.txt`, A2 예시 — API 키 없이 규칙 폴백 상태):

```
╭──────────────── 🤖 LLM 2차 소견(자문) ────────────────╮
│ ⚠️ DNN은 이상탐지했으나 설명가능 규칙이 근거를 내지     │
│ 못함(불일치). 자동판정(gnss_spoofing)은 유지하되,      │
│ 수동·LLM 재검토를 권장한다.                            │
╰─────────────────────────────────────────────────────────╯
```

B3(CAN)는 첫 탐지 시점에 이미 규칙 근거(미등록 ID 25% 등)가 나오기 때문에 이 패널이 **뜨지 않습니다** — "DNN·규칙 불일치"가 아니라서 정상입니다. `ANTHROPIC_API_KEY`를 넣으면 이 박스 안의 문장이 규칙 템플릿 대신 실제 Claude 응답으로 바뀝니다.

### 예상과 달랐던 부분

처음엔 "애매한 경우는 드물어서 `--evasive`를 켜야만 볼 수 있을 것"이라 예상했습니다. 그런데 실제로 돌려보니 다음과 같았습니다:

- **`--evasive` 없이 기본 데모에서도 A2·B2는 거의 항상 2차 소견이 발동**했습니다.
- 이유: DNN이 점진적 공격을 **규칙 임계값(예: INS 잔차 15m)이 쌓이기 전에** 이미 조기탐지해버립니다. 최초 탐지 순간의 잔차값은 아직 4~5m 수준이라 규칙이 근거를 못 냅니다 — "불일치"가 오히려 자연스럽게 자주 발생합니다.
- B3(CAN)는 공격이 급격해서 탐지 즉시 신뢰도가 1.0에 가깝게 포화하고 규칙도 즉시 근거를 내므로 **거의 발동하지 않습니다.**
- 이건 "DNN의 조기탐지 민감도가 설명가능 규칙보다 앞선다"는 실제 현상이고, 바로 그 지점이 LLM 2차 소견이 가치를 더하는 지점이라는, 처음 예상보다 더 좋은 이야기가 됐습니다.

---

## 6. 전체 변경 파일 인벤토리

### 코드 — 수정 (14개, `git diff --stat` 기준)

| 파일                           | 관련 축 | 변경 요약                                                                                                        |
| ---------------------------- | ---- | ------------------------------------------------------------------------------------------------------------ |
| `src/mapping.py`             | ①    | `RESPONSE_TIERS`·`DISRUPTION_WEIGHT`·`HIGH_CONFIDENCE`·`response_tier()`·`playbook_with_tier()` 신규(+94줄)     |
| `src/agents/responder.py`    | ①    | 신뢰도 계산 + tier 선택 로직, LLM 프롬프트에 SLA 근거 추가                                                                     |
| `src/agents/orchestrator.py` | ①③   | SLA 대응강도 표시, 2차 소견 패널/섹션, `evasive` 플래그 배선                                                                   |
| `src/scenarios/a2_gnss.py`   | ①②③  | `confidence` 필드, 잔차추세 규칙 연동, `attack(evasive=)`                                                              |
| `src/scenarios/b2_satcom.py` | ①③   | `confidence` 필드(오차/임계 정규화), `attack(evasive=)`(무시)                                                           |
| `src/scenarios/b3_can.py`    | ①③   | `confidence` 필드, `attack(evasive=)`(무시)                                                                      |
| `src/train.py`               | ①②   | `sla_sweep`/`plot_sla_tradeoff`/`sla_table`(SLA 3함수), `train_gnss_hardened()`, `--adaptive-train` 플래그(+123줄) |
| `src/sim/gnss_sim.py`        | ②    | `SPOOF_PROFILES`, `generate_flight(profile=)`, `generate_dataset(spoof_profiles=)`(+60줄)                     |
| `src/detect/rules.py`        | ②    | `gnss_rule(residual_trend=)` 누적표류 근거                                                                         |
| `src/make_report.py`         | ①②   | 대시보드 `CHARTS`에 `sla_tradeoff.png`/`adaptive_robustness.png` 추가                                               |
| `src/agents/attacker.py`     | ③    | `run(evasive=)` 파라미터 전달                                                                                      |
| `src/tools.py`               | ③    | `simulate_attack_tool(evasive=)` 파라미터 전달                                                                     |
| `src/run_demo.py`            | ③    | `--evasive` CLI 인자                                                                                           |
| `src/agents/detector.py`     | ③    | `_is_ambiguous()`/`_second_opinion()` 신규, tool_use 코드는 롤백 후 원본 구조로 복귀 + 확장                                   |
| `README.md`                  | -    | 코드 실태에 맞춘 문구 정정(로직은 안 건드리고 문구만). 상세는 [§11](#11-readme-문구-정정-기록)                                              |

> **`src/agents/base.py`는 최종 diff에 안 잡힙니다** — 1차 시도에서 `run_with_tools()`를 추가했다가 2차 재설계에서 완전히 롤백해서, 지금은 원본과 **바이트 단위로 동일**합니다(git diff 결과 없음). "손댔다가 되돌린 파일"로 별도 기록해둡니다.

### 코드 — 신규 (1개)

| 파일                     | 내용                                    |
| ---------------------- | ------------------------------------- |
| `src/eval_adaptive.py` | baseline vs hardened 조기탐지율 비교 평가 스크립트 |

### 재생성 산출물 (코드가 자동 생성 — 손으로 쓴 게 아닙니다)

`results/{a2_gnss,b2_satcom,b3_can}/{metrics.md,run_meta.json,*.png}`, `results/demo/*`, `docs/dashboard.html` — `train.py`/`run_demo.py`/`make_report.py`/`eval_adaptive.py`를 실행하면 자동으로 갱신됩니다. 신규 파일: `sla_tradeoff.png`(3개 시나리오) · `adaptive_robustness.{png,md}`(A2).

---

## 7. 직접 돌려보는 법

```powershell
# 가상환경은 이미 만들어져 있습니다(.venv, .gitignore됨) — 재설치 불필요
.\.venv\Scripts\python.exe src\run_demo.py --scenario all              # SLA 대응강도 + 2차 소견 확인
.\.venv\Scripts\python.exe src\run_demo.py --scenario a2_gnss --evasive # 2차 소견이 가장 뚜렷하게 나타남
.\.venv\Scripts\python.exe src\eval_adaptive.py                        # 조기탐지 0.59 vs 0.90 재확인
.\.venv\Scripts\python.exe src\make_report.py                          # docs\dashboard.html 갱신
```

- 모델(`models/*.pt`)과 결과(`results/*`)는 이미 생성돼 있어서, `train.py`를 다시 안 돌려도 위 명령들이 바로 동작합니다.
- `ANTHROPIC_API_KEY`가 없어도 전부 완주합니다(규칙 폴백). 키가 있으면 2차 소견·분석문이 실제 Claude 문장으로 나옵니다.

---

## 8. 정직한 한계 3가지

1. **축① SLA 수치 이득이 작습니다** — 정책(강/약 대응)은 구현됐지만, 이 프로젝트의 DNN들이 워낙 확신에 차 있어서(경보 99%가 신뢰도 0.9 이상) graceful이 발동할 애매한 경우가 드뭅니다. 실제 이득은 탐지가 덜 확실한 실환경에서 더 커질 것으로 예상하지만, 지금 데이터로는 증명하지 못했습니다.
2. **여전히 합성데이터 기반 순환 평가입니다** — 축②로 "훈련 밖 공격"까지는 실험했지만, 그 회피형 공격도 결국 저희가 만든 시뮬레이터의 변형입니다. 실제 외부 데이터(예: 진짜 GPS 스푸핑 로그)로 검증한 것은 아닙니다.
3. **2차 소견 발동 패턴이 예상과 달랐습니다** — "애매한 경우는 드물다"고 예상했는데, A2·B2는 기본 실행에서도 거의 항상 발동합니다(5장 참고). 나쁜 결과는 아니지만, 처음 설계 가정이 틀렸습니다.

---

## 9. 발표 말하기 포인트

- 예선은 보고서 심사지만, 본선은 실시간 공방전과 SLA 채점이 함께 들어갑니다. 축①로 SLA를, 축②로 적대적 강건성을(공격이 탐지기를 회피하려 들 것을 가정), 축③으로 AI 에이전트가 실제 판단에 관여하는 지점을 미리 준비했습니다.
- 축②는 baseline이 회피형 공격에 약해지는 것을 그래프로 그대로 보여줍니다. 약점을 숨기지 않고, 고칠 수단(재학습)도 함께 제시합니다.
- LLM은 판단이 애매할 때만 실제로 관여합니다. 처음엔 형식적인 tool-calling으로 접근했다가 실질적 가치가 없다는 걸 확인하고 재설계했습니다.

---

## 10. 안 건드린 것·제약

- **`requirements.txt`는 절대 수정하지 않았습니다** — 제출용 의존성 고정 파일이라, 검증은 별도 venv 호환 버전으로만 진행했습니다.
- **원본 탐지기·시뮬레이터 로직은 그대로입니다** — `gnss_cnn.py`/`satcom_ae.py`/`can_ids.py`의 신경망 구조나 학습 방식은 하나도 건드리지 않았습니다. `gnss_sim.py`도 기본값(`profile=None`)일 때는 원본과 바이트 단위로 동일합니다.
- **재현성도 그대로입니다** — 위협 분류·SLA tier·모든 지표는 여전히 100% 결정적입니다. LLM은 어디서도 판정을 바꾸지 않고, 서술·자문 역할만 합니다.

---

## 11. README 문구 정정 기록

원본 README에는 실제 코드와 어긋나는 과장된 표현이 일부 있었습니다("LLM이 위협을 분류한다" 등 — 실제로는 DNN+규칙이 결정적으로 분류합니다). 아래 6곳을 코드 실태에 맞게 정정했습니다. **"6단계 킬체인 구동" 표현은 그대로 유지**했습니다 — 콘솔에 실제로 6단계 표가 출력되므로 이건 과장이 아니라 사실이기 때문입니다. **로직은 전혀 건드리지 않고 문구만** 바꿨습니다.

| #   | 위치                             | 원문                                          | 정정 내용                                                           |
| --- | ------------------------------ | ------------------------------------------- | --------------------------------------------------------------- |
| R1  | 소개글(4–5행)                      | "LLM 방어 에이전트가 위협을 분류해 NIST CSF 플레이북으로 대응한다" | "DNN+규칙이 위협을 탐지·분류, LLM은 대응을 지휘(신뢰도로 SLA 대응강도 선택, 애매구간엔 2차 소견)" |
| R2  | 핵심요약(9–12행)                    | "LLM 에이전트가 DNN 탐지기를 도구(tool)로 호출"           | "LLM=서술·지휘, 분류·대응 선택은 DNN+규칙이 결정적" + SLA·적응형 신규 2줄 추가           |
| R3  | 데이터 흐름 그림(24–26행)              | LLM칸 "(위협분류·플레이북 선택)"                       | DNN칸 "(위협분류·신뢰도·근거)" / LLM칸 "(SLA 대응지휘·서술, 애매시 2차소견)"           |
| R4  | Attacker 역할표(45행)              | "6단계 킬체인 구동"                                | 동일 + "(회피형 프로파일 옵션 포함)" 추가                                      |
| R5  | Detector/Responder 역할표(46–47행) | tool 호출 문구                                  | 신뢰도·2차소견(Detector) / SLA 대응강도 선택(Responder) 추가                  |
| R6  | 향후과제(131행)                     | "LLM tool-calling 정식화"                      | "…(현재는 애매구간 2차 소견까지 구현)"                                        |

**원복 방법**: 이 정정은 독립 커밋(`docs(readme): 코드 실태 반영 문구 정정`)으로 분리했습니다. 마음에 안 드는 부분이 있으면 그 커밋 하나만 `git revert`하면 원문으로 완전히 되돌아갑니다. 이 표로도 수동 대조·복원이 가능합니다.
