# 사고보고 — GNSS 스푸핑 — 점진 표류로 항로 탈취

- **시나리오**: `a2_gnss` · 계층 ⑦ PNT
- **위협**: GNSS 스푸핑 (항법 무결성 공격) (무결성(Integrity) — '거짓말시키기')
- **프레임워크 매핑**: MITRE T0830 (AiTM), T0831 (Manipulation of Control) / SPARTA EX-0014.04 (PNT Spoofing)
- **탐지기**: 1D-CNN(다특징 시계열) · 점수 0.789 · 탐지지연 4초

## 증거
| 지표 | 값 |
| --- | --- |
| C/N0(dB-Hz) | 46.6 |
| INS 잔차(m) | 4.5 |
| AGC | 0.52 |
| DOP | 2.13 |
| 위성수 | 12 |

## 규칙 근거(설명가능)
- (DNN 기반 탐지)

## 위협 분석(에이전트)
⑦ PNT 계층에서 1D-CNN(다특징 시계열) 기반 이상 탐지(점수 0.789). 근거: 규칙 임계 미도달(경보는 DNN 기반).

## 대응 플레이북 (NIST CSF)
### 대응(Respond)
- GNSS 입력 차단 → INS 단독 추측항법(dead-reckoning) 전환
- 페일세이프 진입: RTL(자동 귀환) 또는 Loiter(공중 대기)
- 다중 별자리/주파수로 재획득 시도(GPS+Galileo+KPS)
### 복구(Recover)
- 비행로그 항법잔차·위성기하(DOP) 포렌식 → 표류 시작점 역추적
- 스푸핑 구간 시그니처 추출 → 탐지모델 재학습
### 예방·파훼(Protect)
- 신호 인증: Galileo OSNMA / GPS Chimera / M-code
- CRPA 안테나 공간 널링 + GNSS·INS 강결합
- 다중 별자리·다중 주파수 상시 수신

## 지휘 요약(에이전트)
'GNSS 스푸핑 (항법 무결성 공격)' 확정. 즉시조치: GNSS 입력 차단 → INS 단독 추측항법(dead-reckoning) 전환. 이후 복구·근본대응(예방)까지 단계 실행. MITRE T0830 (AiTM), T0831 (Manipulation of Control).
