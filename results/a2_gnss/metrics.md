# A2 · GNSS 스푸핑/재밍 탐지 — 지표

## 요약
| 지표 | 값 |
| --- | --- |
| 전체 정확도 | 0.979 |
| 공격탐지 AUC(공격 vs 정상) | 0.992 |
| TPR@0.5 | 0.950 |
| FPR@0.5 | 0.002 |
| 탐지지연 중앙값(스푸핑) | 4.0 s |
| 탐지지연 중앙값(재밍) | 0.0 s |
| 스푸핑 탐지율 | 1.00 |

## 클래스별 성능
| 클래스 | Precision | Recall | F1 |
| --- | --- | --- | --- |
| 정상 | 0.968 | 0.998 | 0.983 |
| 스푸핑 | 0.996 | 0.913 | 0.953 |
| 재밍 | 0.998 | 0.991 | 0.994 |

## 그림
- `confusion_matrix.png` 혼동행렬
- `roc_attack.png` 공격탐지 ROC
- `detection_latency.png` 탐지지연 분포
- `timeseries_example.png` 점진 표류 vs 탐지시점

## 비고
모델 1D-CNN · 특징 ['cn0_mean', 'cn0_std', 'agc', 'ins_residual', 'dop', 'clock_jump', 'num_sats'] · 윈도 20s · 합성데이터(시드 42).
TEXBAT/OAKBAT 실데이터 연동은 향후과제.
