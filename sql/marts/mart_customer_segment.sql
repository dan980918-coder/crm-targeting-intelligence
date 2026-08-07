-- Grain: 1 row = 1 고객 (전체 22,298,361명)
-- Primary Key: client_id
--
-- CLAUDE.md 17번 "규칙 기반 세그먼트를 먼저 만든다" 원칙에 따라 규칙 기반으로
-- 구축. mart_customer_lifecycle의 8개 상태와 대부분 1:1 대응하되, '탐색_고객'
-- (전체의 87.97%로 지나치게 큼)만 CLAUDE.md 17번이 요구하는 "구매 직전
-- 탐색형" vs "저관여 탐색형"으로 세분화한다.
--
-- 세분화 기준 (데이터 기반, 2026-08-07 갱신 — docs/methodology.md 참고):
-- 탐색_고객 중 n_page_visit >= 10(해당 그룹의 p90, 전환율 변곡점은 아니지만
-- 상위 10% cut + 과접촉 방지라는 실무적 근거는 유효) 이거나 검색을 방문보다
-- 먼저 한 경우(search_first: 검색과 방문을 모두 했고 첫 검색이 첫 방문보다
-- 이른 경우)를 "구매 직전 탐색형"(고관여/고의도)으로 본다.
--
-- 기존에는 n_search_query > 0(검색 1회 이상)만으로 판단했으나, 검색만 하고
-- 방문은 전혀 없는 고객(search_only)의 실제 전환율은 7.75%로 낮은 반면,
-- 검색 후 방문까지 이어진 고객(search_first)은 44.02%로 매우 높아 — 이
-- 둘을 하나의 조건으로 묶으면 저의도 고객까지 고관여로 잘못 분류하게 된다.
-- search_first는 "검색으로 명확한 니즈를 표현한 뒤 실제 상품 탐색(방문)까지
-- 이어간" 행동이라 구매 직전 신호로 보기에 더 타당하다.
--
-- '구매_비활성_위험_고객'과 '비활성_고객'은 세그먼트 레벨에서는
-- '구매_비활성형' 하나로 합친다 — CLAUDE.md 17번이 세그먼트를 8개로
-- 명시했고, recency의 세밀한 구분은 이미 lifecycle에 남아있어 세그먼트
-- 레벨에서 또 나눌 필요가 없다(대시보드 Segment Explorer는 세그먼트를,
-- Lifecycle 페이지는 lifecycle을 보여주는 방식으로 역할 분리).
--
-- 입력: mart_customer_lifecycle, mart_customer_360, stg_search_query, stg_page_visit
-- 출력: Phase 7 대시보드 Segment Explorer, Phase 6 모델 feature(세그먼트 자체를 baseline rule로도 사용)
CREATE OR REPLACE TABLE mart_customer_segment AS
WITH first_search AS (
    SELECT client_id, MIN(event_ts) AS first_search_ts
    FROM stg_search_query
    GROUP BY client_id
),
first_visit AS (
    -- mart_customer_360은 first_visit_ts를 출력 컬럼으로 노출하지 않아 여기서 별도 집계
    SELECT client_id, MIN(event_ts) AS first_visit_ts
    FROM stg_page_visit
    GROUP BY client_id
)
SELECT
    l.client_id,
    l.lifecycle_stage,
    CASE
        WHEN l.lifecycle_stage = '탐색_고객'
             AND (
                 m.n_page_visit >= 10
                 OR (fs.first_search_ts IS NOT NULL
                     AND fv.first_visit_ts IS NOT NULL
                     AND fs.first_search_ts < fv.first_visit_ts)
             )
            THEN '구매_직전_탐색형'
        WHEN l.lifecycle_stage = '탐색_고객'
            THEN '저관여_탐색형'
        WHEN l.lifecycle_stage = '장바구니_고객'
            THEN '장바구니_이탈형'
        WHEN l.lifecycle_stage = '첫_관측_구매_고객'
            THEN '첫_관측_구매_고관여형'
        WHEN l.lifecycle_stage = '활성_구매_고객'
            THEN '안정적_반복구매형'
        WHEN l.lifecycle_stage = '구매_감소_고객'
            THEN '반복구매_감소형'
        WHEN l.lifecycle_stage IN ('구매_비활성_위험_고객', '비활성_고객')
            THEN '구매_비활성형'
        WHEN l.lifecycle_stage = '복귀_고객'
            THEN '복귀형'
        ELSE '기타'
    END AS segment
FROM mart_customer_lifecycle l
JOIN mart_customer_360 m ON l.client_id = m.client_id
LEFT JOIN first_search fs ON l.client_id = fs.client_id
LEFT JOIN first_visit fv ON l.client_id = fv.client_id;
