# 데모 가이드

## 실행
```powershell
# 1) 탐지기 학습(지표·그래프 생성)
python src\train.py --scenario all --docs-dir "..\dev_docu"
# 2) 공격→탐지→대응 오케스트레이션 데모
python src\run_demo.py --scenario all --docs-dir "..\dev_docu"
```

`--scenario` 는 `a2_gnss` / `b2_satcom` / `b3_can` / `all` 중 선택.

## 데모가 보여주는 것
각 시나리오를 **Recon → Attacker(6단계 킬체인) → Detector(DNN+규칙) → Responder(플레이북)** 로 실행하고,
콘솔에 타임라인을, `results/demo`(및 `dev_docu/demo`)에 사고보고를 남긴다.

예시 흐름(콘솔):
```
🔴 Recon    · 대상 GNSS 의존 UAV(민간 L1 C/A 단독…)
🔴 Attacker · 6단계 킬체인 구동(시뮬레이션·오프라인)
🧠 Detector · 1D-CNN 호출 → 🚨 이상탐지 (점수 0.79 · 탐지지연 4초)
🔵 Responder· 위협분류 → 플레이북 (MITRE T0830 / SPARTA EX-0014.04)
             대응: GNSS 차단→INS 단독 / 복구: 로그 포렌식 / 예방: OSNMA·CRPA
```

## LLM(Claude) 활성화
- 기본은 **규칙 폴백**(오프라인 완주). `ANTHROPIC_API_KEY` 환경변수가 있으면
  방어 에이전트의 위협분석·지휘요약이 **Claude로 자동 업그레이드**된다.
  ```powershell
  setx ANTHROPIC_API_KEY "sk-ant-..."   # 새 터미널에서 적용
  ```
- 모델은 `config.yaml`의 `llm.model`(기본 `claude-haiku-4-5`).

## 산출물(보고서용)
- `dev_docu/A2_gnss`·`B2_satcom`·`B3_can` : 지표표(metrics.md)·그림(ROC/혼동행렬/탐지지연)·run_meta.json
- `dev_docu/demo` : 사고보고(incident_*.md)·오케스트레이션 타임라인
- `dev_docu/00_overview/architecture.png` : 시스템 다이어그램

> 데모 영상(선택): 위 명령 실행 화면을 녹화해 YouTube/Vimeo unlisted로 첨부 가능.
