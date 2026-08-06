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

(아직 미구현)
