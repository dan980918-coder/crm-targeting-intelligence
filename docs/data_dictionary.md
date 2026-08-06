# Data Dictionary — SQL 레이어 테이블 문서

CLAUDE.md 12번 원칙에 따라 각 테이블의 목적·Grain·PK·FK·컬럼·생성 SQL·갱신
방식·품질 테스트·입출력 테이블을 기록한다. Phase가 진행됨에 따라
intermediate/mart 섹션을 계속 추가한다.

---

## Staging Layer

모든 staging 테이블은 원본 Parquet(`data/raw/synerise_dataset/`)을 VIEW로
lazy 참조한다 (materialize하지 않음 — Phase 1 원칙: 전체를 메모리/디스크에
중복 저장하지 않는다). 갱신 방식은 뷰 재정의이므로 원본 Parquet이 바뀌면
자동 반영된다.

### stg_product_buy

- **목적**: product_buy 원본 이벤트를 타입 캐스팅 + 버스트 플래그 추가해 정제
- **Grain**: 1행 = 1 product_buy 이벤트 (client_id, event_ts, sku 조합, 원본과 1:1)
- **Primary Key**: 없음 (원본 자체가 PK 후보 (client_id, timestamp, sku)로도 유일하지 않음 — Phase 1 8.2)
- **Foreign Key**: `sku` → `stg_product_properties.sku`
- **컬럼**:
  | 컬럼 | 타입 | 정의 |
  |---|---|---|
  | client_id | BIGINT | 고객 ID |
  | event_ts | TIMESTAMP | 구매 시각 (원본 VARCHAR에서 TRY_CAST) |
  | sku | BIGINT | 상품 ID |
  | is_burst_repeat_5s | BOOLEAN | 동일 (client_id, sku)의 직전 이벤트와 5초 이내 반복이면 TRUE (Phase 1 8.6 결정) |
- **생성 SQL**: `sql/staging/stg_product_buy.sql`
- **갱신 방식**: VIEW (원본 Parquet 변경 시 자동 반영, 별도 배치 불필요)
- **품질 테스트**: `tests/data_quality/test_staging.py` — 행 수/버스트 비율이 Phase 1 수치와 일치하는지, 결측 없는지, timestamp 캐스팅 실패 없는지 검증
- **입력**: `data/raw/synerise_dataset/product_buy.parquet`
- **출력**: intermediate 레이어(`int_customer_purchase_history` 등, 예정)에서 참조

### stg_add_to_cart / stg_remove_from_cart

- **목적/Grain/컬럼**: stg_product_buy와 동일 구조 (client_id, event_ts, sku, is_burst_repeat_5s)
- **PK**: 없음 (원본 PK 후보 유일하지 않음)
- **FK**: `sku` → `stg_product_properties.sku`
- **생성 SQL**: `sql/staging/stg_add_to_cart.sql`, `sql/staging/stg_remove_from_cart.sql`
- **입력**: `add_to_cart.parquet`, `remove_from_cart.parquet`

### stg_page_visit

- **목적**: page_visit 원본 이벤트 정제
- **Grain**: 1행 = 1 page_visit 이벤트
- **컬럼**: client_id, event_ts, `url`(BIGINT, 익명 숫자 ID — **sku와 연결 불가**, Phase 1 8.9/`docs/methodology.md`), is_burst_repeat_5s (동일 client_id+url 5초 이내 반복)
- **PK/FK**: 없음. url은 어떤 다른 테이블과도 조인 키가 아님
- **생성 SQL**: `sql/staging/stg_page_visit.sql`
- **입력**: `page_visit.parquet` (199,451,980행 — 가장 큰 테이블, VIEW로만 유지해 메모리 부담 방지)

### stg_search_query

- **목적**: search_query 원본 이벤트 정제
- **Grain**: 1행 = 1 search_query 이벤트
- **컬럼**: client_id, event_ts, `query`(VARCHAR, 16차원 양자화 임베딩 — 해석 가능한 원문 아님, Phase 1 8.2), is_burst_repeat_5s (item 키가 없어 client_id 기준으로만 계산)
- **PK/FK**: 없음
- **생성 SQL**: `sql/staging/stg_search_query.sql`
- **입력**: `search_query.parquet`

### stg_product_properties

- **목적**: 상품 차원(dimension) 테이블 정제
- **Grain**: 1행 = 1 sku
- **Primary Key**: `sku` (Phase 1 8.5에서 유일성 확인, 완전한 PK)
- **컬럼**:
  | 컬럼 | 타입 | 정의 |
  |---|---|---|
  | sku | BIGINT | 상품 ID (PK) |
  | category | BIGINT | 카테고리 ID |
  | price_bucket | BIGINT | 가격 구간 0~99 (**실제 금액 아님**, Phase 1 8.5) — 원본 컬럼명 `price`를 명시적으로 리네임 |
  | name_embedding | VARCHAR | 16차원 양자화 임베딩 (원본 컬럼명은 `name`이나 공식 문서상 `embedding`에 해당 — Phase 1 8.2) — 리네임으로 혼동 방지 |
- **생성 SQL**: `sql/staging/stg_product_properties.sql`
- **입력**: `product_properties.parquet`

---

## Intermediate Layer

모든 intermediate 테이블은 `CREATE OR REPLACE TABLE`로 **materialize**한다
(staging의 VIEW와 다름 — 반복 집계 비용이 커서 저장해두는 것이 실용적).
`data/processed/crm.duckdb`에 저장되며 `.gitignore` 대상.

> **중요 발견 (2026-08-05)**: 고객의 연속된 product_buy 이벤트 중
> **63.72%가 직전 이벤트와 정확히 동일한 timestamp**를 갖는다 — 한 번의
> 결제(order)에 여러 상품이 담기면 상품별로 별도 행이 생기되 타임스탬프는
> 동일하기 때문으로 추정된다. 이를 무시하고 원본 행 단위로 구매 간격을
> 계산하면 평균 구매 간격이 22.95일이 아니라 8.32일로 왜곡된다(약 2.76배
> 축소). 따라서 "구매 순번/간격" 관련 컬럼은 반드시 DISTINCT
> (client_id, event_ts) = "구매 occasion" 단위로 계산해야 하며,
> `int_customer_purchase_history`/`int_customer_purchase_gap` 모두 이 정의를
> 따른다 (Phase 1 8.7 검증 스크립트의 `ts != prev_ts` 필터와 동일 정의로
> 맞춤). 이 발견은 버그 수정 사항이며 별도 사용자 확인 없이 즉시 정정함
> (전처리 재량 판단이 아니라 통계 정의 오류 교정).

### int_customer_purchase_history

- **목적**: product_buy 원본 이벤트에 구매 occasion 순번·간격 enrichment
- **Grain**: 1행 = 1 product_buy 원본 이벤트 (stg_product_buy와 1:1, 2,318,502행)
- **Primary Key**: 없음 (원본이 유일하지 않음)
- **Foreign Key**: client_id, sku
- **컬럼**:
  | 컬럼 | 정의 |
  |---|---|
  | raw_row_seq | 고객 내 원본 행 기준 순번 (line-item 단위) |
  | purchase_occasion_seq | 고객 내 **구매 occasion**(distinct timestamp) 기준 순번 |
  | days_since_prev_purchase_occasion | 직전 구매 occasion과의 간격(일) — 같은 occasion 내 다른 상품 행은 동일 값 공유 |
  | is_first_observed_purchase | 해당 행이 첫 번째 구매 occasion에 속하는지 |
- **생성 SQL**: `sql/intermediate/int_customer_purchase_history.sql`
- **품질 테스트**: `tests/data_quality/test_intermediate.py` — 행 수 일치, pooled mean/median gap이 Phase 1(22.9463일/9.4827일)과 일치, 음수 간격 없음
- **입력**: stg_product_buy / **출력**: int_customer_purchase_gap, Phase 5 feature

### int_customer_purchase_gap

- **목적**: 고객별 구매 빈도·간격 요약
- **Grain**: 1행 = 1 구매 고객 (909,210행)
- **Primary Key**: client_id
- **컬럼**: n_purchases(원본 행 수 기준, Phase1 "구매 이벤트 수"와 동일 정의), n_purchase_days(고유 구매일), first/last_purchase_ts, avg/stddev/min/max_purchase_gap_days(occasion 단위)
- **생성 SQL**: `sql/intermediate/int_customer_purchase_gap.sql`
- **입력**: stg_product_buy (독립 계산, purchase_history에 비의존적) / **출력**: Phase 3, Phase 5

### int_customer_daily_activity

- **목적**: 고객×일자 단위 활동량 롤업 (5개 이벤트 타입 통합)
- **Grain**: 1행 = 1 고객 × 1 활동일 (46,896,180행)
- **Primary Key**: (client_id, activity_date)
- **컬럼**: n_page_visit, n_search_query, n_add_to_cart, n_remove_from_cart, n_product_buy, n_events_total, n_event_types_active
- **생성 SQL**: `sql/intermediate/int_customer_daily_activity.sql`
- **품질 테스트**: n_events_total 합계가 원본 5개 테이블 총 행수(226,758,312)와 일치
- **입력**: 5개 stg_* / **출력**: Phase 3(활동 리텐션), Phase 5(일별 feature)

### int_customer_cart_behavior

- **목적**: 고객별 장바구니 추가/제거/전환 요약
- **Grain**: 1행 = 1 고객 (add 또는 remove 중 하나라도 있는 고객, 2,359,888행)
- **Primary Key**: client_id
- **컬럼**: n_add, n_add_distinct_sku, first/last_add_ts, n_remove, n_remove_distinct_sku, first/last_remove_ts, n_add_to_buy_pairs, avg_hours_add_to_buy
- **생성 SQL**: `sql/intermediate/int_customer_cart_behavior.sql`
- **품질 테스트**: 행 수가 8.4 교집합/합집합 산술(2,333,463+694,391−667,966)과 일치
- **입력**: stg_add_to_cart, stg_remove_from_cart, stg_product_buy / **출력**: Phase 3(장바구니 이탈), Phase 5

### int_customer_category_behavior

- **목적**: 고객×카테고리 단위 구매 요약
- **Grain**: 1행 = 1 고객 × 1 카테고리 (구매 이력 있는 조합만, 1,544,917행)
- **Primary Key**: (client_id, category)
- **Foreign Key**: category → stg_product_properties.category
- **컬럼**: n_purchases, n_distinct_sku, first/last_purchase_ts
- **생성 SQL**: `sql/intermediate/int_customer_category_behavior.sql`
- **입력**: stg_product_buy, stg_product_properties / **출력**: Phase 3(카테고리 퍼널), Phase 5

### int_customer_observation_period

- **목적**: 고객별 관찰기간·검열(censoring) 진단
- **Grain**: 1행 = 1 고객 (전체 22,298,361행)
- **Primary Key**: client_id
- **컬럼**: first_event_ts, last_event_ts, observation_days, n_active_days, is_left_censor_candidate(좌측 7일 창), is_right_censor_candidate(우측 14일 창)
- **참고**: 우측 검열 문제 자체의 실제 처리는 이 테이블의 플래그가 아니라 Phase 5
  `mart_customer_snapshot`의 snapshot_date 제한 설계로 원천 차단하기로 이미 결정됨
  (`docs/methodology.md` 2026-08-05 항목). 이 테이블은 진단/참고용.
- **생성 SQL**: `sql/intermediate/int_customer_observation_period.sql`
- **입력**: 5개 stg_* / **출력**: Phase 5 스냅샷 설계 참고

## Mart Layer

CLAUDE.md 11번이 요구하는 11개 mart 테이블 중, 라이프사이클·세그먼트·이탈
기준처럼 아직 확정되지 않은 값에 의존하지 않는 **5개만 우선 구축**했다.
나머지 6개(`mart_customer_lifecycle`, `mart_customer_segment`,
`mart_customer_snapshot`, `mart_churn_target`, `mart_purchase_propensity`,
`mart_targeting_simulation`)는 Phase 3(퍼널·코호트·리텐션 실제 분포 확인)
이후 해당 기준을 사용자와 함께 정할 때까지 대기한다.

### mart_customer_360

- **목적**: 고객별 전체 활동 요약 (라이프사이클/세그먼트 컬럼은 아직 없음 — Phase 4에서 추가 예정)
- **Grain**: 1행 = 1 고객 (전체 22,298,361행)
- **Primary Key**: client_id
- **컬럼**: first/last_event_ts, observation_days, n_active_days, is_left/right_censor_candidate, n_page_visit, n_search_query, n_add_to_cart, n_remove_from_cart, n_purchases, n_purchase_days, first/last_purchase_ts, avg_purchase_gap_days, is_buyer, has_cart_activity, is_repeat_capable
- **생성 SQL**: `sql/marts/mart_customer_360.sql`
- **검증**: is_buyer 909,210명 / has_cart_activity 2,359,888명 / is_repeat_capable 210,633명 — 전부 Phase 1 수치와 정확히 일치 확인
- **입력**: int_customer_observation_period, int_customer_purchase_gap, int_customer_cart_behavior, stg_page_visit, stg_search_query

### mart_customer_daily

- **목적**: int_customer_daily_activity를 마트로 승격 (현재는 동일 내용)
- **Grain**: 1행 = 1 고객 × 1 활동일 (46,896,180행) / **PK**: (client_id, activity_date)
- **생성 SQL**: `sql/marts/mart_customer_daily.sql`

### mart_customer_weekly

- **목적**: 주 단위 활동 롤업
- **Grain**: 1행 = 1 고객 × 1 활동주(week_start, 월요일 기준, 38,347,783행) / **PK**: (client_id, week_start)
- **컬럼**: n_page_visit, n_search_query, n_add_to_cart, n_remove_from_cart, n_product_buy, n_events_total, n_active_days_in_week
- **생성 SQL**: `sql/marts/mart_customer_weekly.sql`
- **입력**: int_customer_daily_activity

### mart_customer_cohort

- **목적**: "첫 관측 구매 주차" 코호트 배정 (CLAUDE.md 14번 고정 정의)
- **Grain**: 1행 = 1 구매 고객 (909,210행) / **PK**: client_id
- **컬럼**: first_purchase_ts, cohort_week, n_purchases, n_purchase_days, avg_purchase_gap_days
- **생성 SQL**: `sql/marts/mart_customer_cohort.sql`

### mart_customer_retention

- **목적**: 코호트별 7/14/28일 재구매율 (CLAUDE.md 14번 고정 지표)
- **Grain**: 1행 = 1 cohort_week (25개 주차) / **PK**: cohort_week
- **컬럼**: n_customers_in_cohort, repurchase_7d/14d/28d_rate, avg_purchase_days, avg_category_diversity, is_7d/14d/28d_window_censored
- **중요**: 우측 검열로 인해 마지막 4개 코호트(2022-11-14 이후)는 하나 이상의
  플래그가 TRUE — 해당 코호트의 재구매율은 과소추정된 값이므로 Phase 3
  해석·시각화 시 반드시 구분 표시할 것 (`docs/decisions_pending_review.md`
  2026-08-05 "코호트별 재구매율의 우측 검열 처리" 항목 참고)
- **생성 SQL**: `sql/marts/mart_customer_retention.sql`
- **입력**: mart_customer_cohort, int_customer_purchase_history, int_customer_category_behavior, int_customer_observation_period

### mart_customer_lifecycle

- **목적**: 관측 종료 시점(2022-12-08) 기준 고객 라이프사이클 상태 분류
- **Grain**: 1행 = 1 고객 (전체 22,298,361행) / **PK**: client_id
- **컬럼**: is_buyer, n_purchase_days, days_since_last_purchase, gap_before_last_purchase, lifecycle_stage
- **lifecycle_stage 값**(8개, CLAUDE.md 16번 후보 9개 중 반복구매/활성구매를 하나로 통합):
  `탐색_고객`, `장바구니_고객`, `첫_관측_구매_고객`, `활성_구매_고객`, `구매_감소_고객`, `구매_비활성_위험_고객`, `비활성_고객`, `복귀_고객`
- **임계값 근거** (데이터 기반, 자세한 내용은 `docs/methodology.md` 참고):
  14일 = 구매간격 중앙값(9.48일) × 1.5, 28일 = 중앙값 × 3, 60일 ≈ 구매간격 p90(68.05일).
  CLAUDE.md 18번이 "비교 대상"으로 제시한 14일/28일과 정확히 일치.
- **분포** (2026-08-05 빌드 기준):

  | 상태 | 고객 수 | 비율 |
  |---|---:|---:|
  | 탐색_고객 | 19,616,700 | 87.97% |
  | 장바구니_고객 | 1,772,451 | 7.95% |
  | 비활성_고객 | 489,174 | 2.19% |
  | 구매_비활성_위험_고객 | 179,620 | 0.81% |
  | 구매_감소_고객 | 102,363 | 0.46% |
  | 첫_관측_구매_고객 | 82,368 | 0.37% |
  | 활성_구매_고객 | 31,553 | 0.14% |
  | 복귀_고객 | 24,132 | 0.11% |

- **생성 SQL**: `sql/marts/mart_customer_lifecycle.sql`
- **품질 테스트**: `tests/data_quality/test_lifecycle.py` — 미분류(기타) 0건, 구매 상태 합계=909,210, 비구매 상태 합계=21,389,151, 음수 recency 0건
- **입력**: mart_customer_360, int_customer_observation_period, int_customer_purchase_history
- **출력**: mart_customer_segment, Phase 7 대시보드 Lifecycle 페이지

### 대기 중인 mart 테이블

| 테이블 | 대기 사유 |
|---|---|
| mart_customer_segment | mart_customer_lifecycle 기반으로 다음 단계에서 구축 예정 |
| mart_customer_snapshot | Feature/Label Window 구조는 결정됨(`docs/methodology.md`) — 다음 단계에서 구축 |
| mart_churn_target | mart_customer_snapshot 이후 구축 (14/28일 기준은 이미 위 lifecycle 임계값과 동일 근거로 확정됨) |
| mart_purchase_propensity | mart_churn_target과 함께 구축 예정 |
| mart_targeting_simulation | Phase 6 모델 결과가 있어야 의미 있는 시뮬레이션 가능 — 모델링 단계까지 대기 |
