-- Grain: 1 row = 1 고객 x 1 snapshot_date
-- Primary Key: (client_id, snapshot_date)
--
-- CLAUDE.md 19번 Model B("향후 구매 가능성", "활동 고객" 대상)의 타겟
-- 테이블. mart_churn_target(구매 이력 있는 고객만 대상)과 달리, 아직 한 번도
-- 구매하지 않았지만 구매 가능성이 있는 고객(예: 방문/검색이 활발한 탐색
-- 고객)까지 포함한다 — 그렇지 않으면 이 라벨이 churn 라벨의 단순 반전에
-- 불과해져 별도 모델을 만들 이유가 없어진다.
--
-- 모집단 정의("활동 고객"의 데이터 기반 해석): snapshot_date 이전 누적
-- 기준으로 (a) 방문 10회 이상 (Phase 4 세그먼트에서 이미 사용한 p90 기준과
-- 동일선상) 또는 (b) 검색 1회 이상(탐색_고객의 90%가 검색을 전혀 안 해
-- 이례적 신호) 또는 (c) 장바구니 추가 이력 또는 (d) 구매 이력. 순수
-- 1~2회성 방문자(전체의 76.89%, 저관여_탐색형)는 제외 — 전환 가능성이
-- 사실상 0에 가까운 트래픽을 propensity 모델링에 포함하지 않는 것은
-- 실무에서도 흔한 관행이며, 계산 비용도 크게 줄인다.
--
-- 효율성: 원본 199M행 page_visit을 다시 스캔하지 않고, 이미 만들어진
-- int_customer_daily_activity(46.9M행, client x date 집계)를 재사용한다.
--
-- avg_category_repurchase_rate (2026-08-08 추가): mart_customer_snapshot과
-- 동일한 lookup(int_customer_category_repurchase_avg_by_snapshot)을 재사용.
-- 처음엔 이 mart 안에서 직접 계산했으나, 기존 activity_before 조인(46.9M행
-- int_customer_daily_activity 기반)과 한 쿼리 플랜에서 합쳐지며 8GB 환경에서
-- OOM이 발생해 별도 intermediate 테이블 + 가벼운 LEFT JOIN으로 분리했다.
-- 구매 이력이 없는 후보 고객(방문/검색/장바구니만 있는 경우)은 정의상
-- NULL — "정보 없음"과 "재구매 안 함(0)"을 구분해야 하므로 0으로 대체하지 않음.
--
-- 입력: mart_customer_360, int_customer_daily_activity, int_customer_purchase_history,
--       int_customer_category_repurchase_avg_by_snapshot
-- 출력: Phase 6 모델 B 학습/평가
--
-- 구현 노트: 이 파일은 두 단계 CREATE TABLE로 나뉜다. avg_category_repurchase_rate
-- LEFT JOIN까지 한 번의 쿼리 플랜에 넣으면(원래 시도) activity_before의
-- 기존 무거운 조인과 합쳐지며 8GB 환경에서 OOM이 발생했다. 1단계에서 기존
-- 로직을 먼저 디스크에 완전히 materialize하고, 2단계에서 그 결과 테이블에
-- 가벼운 LEFT JOIN 하나만 추가하는 방식으로 우회했다.
CREATE OR REPLACE TABLE mart_purchase_propensity_base AS
WITH bounds AS (
    SELECT MAX(last_event_ts) AS window_max, MIN(first_event_ts) AS window_min
    FROM int_customer_observation_period
),
snapshot_dates AS (
    SELECT CAST(gs AS DATE) AS snapshot_date
    FROM bounds, generate_series(
        CAST(window_min AS DATE) + INTERVAL 28 DAY,
        CAST(window_max AS DATE) - INTERVAL 28 DAY,
        INTERVAL 14 DAY
    ) AS t(gs)
),
candidate_ids AS (
    -- 전체 관측기간 기준 상한 후보(5,152,642명) — 이후 snapshot_date별로 더 좁혀짐
    SELECT client_id FROM mart_customer_360
    WHERE n_page_visit >= 10 OR n_search_query >= 1 OR has_cart_activity OR is_buyer
),
cand_daily AS (
    SELECT d.*
    FROM int_customer_daily_activity d
    JOIN candidate_ids c ON d.client_id = c.client_id
),
cand_purchase_occasions AS (
    SELECT DISTINCT h.client_id, h.event_ts
    FROM int_customer_purchase_history h
    JOIN candidate_ids c ON h.client_id = c.client_id
),
activity_before AS (
    SELECT
        sd.snapshot_date,
        d.client_id,
        SUM(d.n_page_visit) AS cum_visits,
        SUM(d.n_search_query) AS cum_search,
        SUM(d.n_add_to_cart) AS cum_cart_add,
        SUM(CASE WHEN d.activity_date >= sd.snapshot_date - INTERVAL 28 DAY
                 THEN d.n_page_visit ELSE 0 END) AS n_page_visit_28d,
        SUM(CASE WHEN d.activity_date >= sd.snapshot_date - INTERVAL 28 DAY
                 THEN d.n_search_query ELSE 0 END) AS n_search_query_28d,
        SUM(CASE WHEN d.activity_date >= sd.snapshot_date - INTERVAL 28 DAY
                 THEN d.n_add_to_cart ELSE 0 END) AS n_add_to_cart_28d,
        SUM(CASE WHEN d.activity_date >= sd.snapshot_date - INTERVAL 28 DAY
                 THEN d.n_remove_from_cart ELSE 0 END) AS n_remove_from_cart_28d
    FROM snapshot_dates sd
    JOIN cand_daily d ON d.activity_date < sd.snapshot_date
    GROUP BY sd.snapshot_date, d.client_id
),
purchase_before AS (
    SELECT
        sd.snapshot_date,
        po.client_id,
        MAX(po.event_ts) AS last_purchase_ts,
        COUNT(*) AS n_purchase_occasions_so_far
    FROM snapshot_dates sd
    JOIN cand_purchase_occasions po ON po.event_ts < sd.snapshot_date
    GROUP BY sd.snapshot_date, po.client_id
),
population AS (
    SELECT snapshot_date, client_id FROM activity_before
    WHERE cum_visits >= 10 OR cum_search >= 1 OR cum_cart_add > 0
    UNION
    SELECT snapshot_date, client_id FROM purchase_before
),
label_calc AS (
    SELECT
        p.snapshot_date,
        p.client_id,
        MAX(CASE WHEN po.event_ts > p.snapshot_date
                  AND po.event_ts <= p.snapshot_date + INTERVAL 14 DAY
             THEN 1 ELSE 0 END) AS will_purchase_14d,
        MAX(CASE WHEN po.event_ts > p.snapshot_date
                  AND po.event_ts <= p.snapshot_date + INTERVAL 28 DAY
             THEN 1 ELSE 0 END) AS will_purchase_28d
    FROM population p
    LEFT JOIN cand_purchase_occasions po ON p.client_id = po.client_id
    GROUP BY p.snapshot_date, p.client_id
)
SELECT
    p.snapshot_date,
    p.client_id,
    (pb.client_id IS NOT NULL) AS has_purchase_history,
    pb.last_purchase_ts,
    CASE WHEN pb.last_purchase_ts IS NOT NULL
         THEN date_diff('day', pb.last_purchase_ts, p.snapshot_date) END AS days_since_last_purchase,
    COALESCE(pb.n_purchase_occasions_so_far, 0) AS n_purchase_occasions_so_far,
    COALESCE(ab.n_page_visit_28d, 0) AS n_page_visit_28d,
    COALESCE(ab.n_search_query_28d, 0) AS n_search_query_28d,
    COALESCE(ab.n_add_to_cart_28d, 0) AS n_add_to_cart_28d,
    COALESCE(ab.n_remove_from_cart_28d, 0) AS n_remove_from_cart_28d,
    lc.will_purchase_14d,
    lc.will_purchase_28d
FROM population p
LEFT JOIN purchase_before pb ON p.snapshot_date = pb.snapshot_date AND p.client_id = pb.client_id
LEFT JOIN activity_before ab ON p.snapshot_date = ab.snapshot_date AND p.client_id = ab.client_id
JOIN label_calc lc ON p.snapshot_date = lc.snapshot_date AND p.client_id = lc.client_id;

CREATE OR REPLACE TABLE mart_purchase_propensity AS
SELECT
    base.* EXCLUDE (will_purchase_14d, will_purchase_28d),
    car.avg_category_repurchase_rate,
    base.will_purchase_14d,
    base.will_purchase_28d
FROM mart_purchase_propensity_base base
LEFT JOIN int_customer_category_repurchase_avg_by_snapshot car
    ON base.snapshot_date = car.snapshot_date AND base.client_id = car.client_id;

DROP TABLE mart_purchase_propensity_base;
