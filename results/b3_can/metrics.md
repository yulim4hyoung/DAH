# B3 · CAN 침입탐지 — 지표

## 요약
| 지표 | 값 |
| --- | --- |
| 전체 정확도 | 0.999 |
| macro-F1 | 0.999 |
| 공격탐지 AUC | 1.000 |
| 데이터 출처 | synthetic |

## 클래스별 성능
| 클래스 | Precision | Recall | F1 |
| --- | --- | --- | --- |
| 정상 | 0.996 | 1.000 | 0.998 |
| DoS | 1.000 | 0.996 | 0.998 |
| 퍼지 | 1.000 | 1.000 | 1.000 |
| 스푸핑 | 1.000 | 1.000 | 1.000 |

## 그림
- `confusion_matrix.png` 4클래스 혼동행렬
- `per_class_f1.png` 클래스별 F1
- `roc_attack.png` 공격탐지 ROC

## 비고
경량 MLP · 윈도 특징 ['mean_iat', 'std_iat', 'min_iat', 'n_unique_id', 'max_id_freq', 'id_entropy', 'known_id_ratio', 'mean_dlc'].
데이터: synthetic (실 Car-Hacking CSV를 data/can/ 에 두면 자동 사용, 없으면 동형 합성).
