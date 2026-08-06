# Model Card — Model B: 향후 구매 가능성(Propensity) 예측

## 개요
- **목적**: 활동 고객(구매 이력 없는 고관여 탐색/장바구니 고객 포함)이 기준일 이후 14일/28일 내 구매할지 예측
- **모집단**: `mart_purchase_propensity` (snapshot_date 이전 누적 방문≥10 또는 검색≥1 또는 장바구니/구매 이력)
- **최종 모델**: LightGBM (500 rounds, val AUC 기준 조기종료)
- **비교 대상**: 무작위, 전체평균, 최근성 규칙, 구매빈도 규칙, 방문검색 규칙, 로지스틱 회귀

## 데이터
- 학습/검증/테스트 기간: Model A와 동일한 snapshot_date 경계 사용(직접 비교 가능하도록)
- Feature Window: snapshot_date 이전 28일 / Label Window: 이후 14일 또는 28일

## Feature (7개)
has_purchase_history, days_since_last_purchase, n_purchase_occasions_so_far,
n_page_visit_28d, n_search_query_28d, n_add_to_cart_28d, n_remove_from_cart_28d

## 성능 (test, LightGBM)

| 라벨 | AUC | PR-AUC | Lift@10% | 실제 양성률 |
|---|---:|---:|---:|---:|
| will_purchase_14d | 0.867 | 0.159 | 6.30 | 1.3% |
| will_purchase_28d | 0.860 | 0.239 | 6.03 | 2.5% |

## 한계 및 주의사항
- 모집단이 "활동 고객" 중 일부(방문 10회 이상/검색/장바구니/구매 이력)로
  한정됨 — 완전 무작위 방문자(전체의 76.89%)는 제외해 전환 가능성이
  낮은 트래픽은 다루지 않음(`docs/data_dictionary.md` mart_purchase_propensity 항목)
- Model A와 Lift 수치를 직접 비교하면 안 됨(라벨 기저율이 달라 상한이
  다름) — `reports/phase6_modeling_results.md` "Lift 해석에 대한 일반적 교훈" 참고
- 실제 캠페인 전환율 개선은 검증되지 않음 (CLAUDE.md 5번)

## 재현
`python3 scripts/train_model_b.py`
