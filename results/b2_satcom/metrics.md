# B2 · SATCOM 관리망 이상탐지 — 지표

## 요약
| 지표 | 값 |
| --- | --- |
| 이상탐지 AUC | 0.984 |
| Precision | 0.977 |
| Recall(TPR) | 0.940 |
| F1 | 0.958 |
| FPR@임계 | 0.011 |
| 탐지지연 중앙값 | 2.0 버킷(분) |
| 공격윈도 탐지율 | 1.00 |

## SLA 트레이드오프(가용성)
| 임계 | 공격탐지율 | 경보율 | 서비스방해(일괄차단) | 서비스방해(게이팅) |
| --- | --- | --- | --- | --- |
| 0.50 | 0.940 | 0.313 | 0.313 | 0.311 |
| 0.70 | 0.940 | 0.311 | 0.311 | 0.311 |
| 0.90 | 0.939 | 0.309 | 0.309 | 0.309 |

> 신뢰도 게이팅(신뢰도<0.7 완화)이 관리망 오차단으로 인한 BLOS 링크 중단을 낮춘다.

## 그림
- `recon_error_hist.png` 정상 vs 공격 재구성오차 분포+임계
- `roc.png` 이상탐지 ROC
- `timeline_example.png` AcidRain형 전개 vs 탐지시점
- `sla_tradeoff.png` SLA 트레이드오프

## 비고
비지도 오토인코더(정상만 학습) · 특징 ['cmd_rate', 'cmd_type_entropy', 'fw_push', 'distinct_modems', 'auth_fail', 'config_change', 'modems_offline', 'offhours'].
임계=정상 재구성오차 99%tile. 합성데이터(시드 42).
