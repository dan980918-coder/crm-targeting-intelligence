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

(아직 미구현 — Phase 2 다음 단계에서 작성 예정)

## Mart Layer

(아직 미구현)
