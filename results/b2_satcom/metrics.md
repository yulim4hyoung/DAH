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

## 그림
- `recon_error_hist.png` 정상 vs 공격 재구성오차 분포+임계
- `roc.png` 이상탐지 ROC
- `timeline_example.png` AcidRain형 전개 vs 탐지시점

## 비고
비지도 오토인코더(정상만 학습) · 특징 ['cmd_rate', 'cmd_type_entropy', 'fw_push', 'distinct_modems', 'auth_fail', 'config_change', 'modems_offline', 'offhours'].
임계=정상 재구성오차 99%tile. 합성데이터(시드 42).
