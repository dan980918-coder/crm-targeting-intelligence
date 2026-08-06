-- Grain: 1 row = 1 고객 (add_to_cart 또는 remove_from_cart 중 하나라도 있는 고객)
-- Primary Key: client_id
-- 입력: stg_add_to_cart, stg_remove_from_cart, stg_product_buy
-- 출력: Phase 3(장바구니 이탈 분석), Phase 5(feature) 참조 예정
CREATE OR REPLACE TABLE int_customer_cart_behavior AS
WITH add_summary AS (
    SELECT
        client_id,
        COUNT(*) AS n_add,
        COUNT(DISTINCT sku) AS n_add_distinct_sku,
        MIN(event_ts) AS first_add_ts,
        MAX(event_ts) AS last_add_ts
    FROM stg_add_to_cart
    GROUP BY client_id
),
remove_summary AS (
    SELECT
        client_id,
        COUNT(*) AS n_remove,
        COUNT(DISTINCT sku) AS n_remove_distinct_sku,
        MIN(event_ts) AS first_remove_ts,
        MAX(event_ts) AS last_remove_ts
    FROM stg_remove_from_cart
    GROUP BY client_id
),
add_first AS (
    SELECT client_id, sku, MIN(event_ts) AS add_ts FROM stg_add_to_cart GROUP BY client_id, sku
),
buy_first AS (
    SELECT client_id, sku, MIN(event_ts) AS buy_ts FROM stg_product_buy GROUP BY client_id, sku
),
conv AS (
    SELECT
        a.client_id,
        COUNT(*) AS n_add_to_buy_pairs,
        AVG(date_diff('second', a.add_ts, b.buy_ts) / 3600.0) AS avg_hours_add_to_buy
    FROM add_first a
    JOIN buy_first b ON a.client_id = b.client_id AND a.sku = b.sku
    WHERE b.buy_ts >= a.add_ts
    GROUP BY a.client_id
)
SELECT
    COALESCE(a.client_id, r.client_id) AS client_id,
    COALESCE(a.n_add, 0) AS n_add,
    COALESCE(a.n_add_distinct_sku, 0) AS n_add_distinct_sku,
    a.first_add_ts,
    a.last_add_ts,
    COALESCE(r.n_remove, 0) AS n_remove,
    COALESCE(r.n_remove_distinct_sku, 0) AS n_remove_distinct_sku,
    r.first_remove_ts,
    r.last_remove_ts,
    COALESCE(c.n_add_to_buy_pairs, 0) AS n_add_to_buy_pairs,
    c.avg_hours_add_to_buy
FROM add_summary a
FULL OUTER JOIN remove_summary r ON a.client_id = r.client_id
LEFT JOIN conv c ON COALESCE(a.client_id, r.client_id) = c.client_id;
