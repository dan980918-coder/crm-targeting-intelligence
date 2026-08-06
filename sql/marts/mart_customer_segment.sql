-- Grain: 1 row = 1 고객 (전체 22,298,361명)
-- Primary Key: client_id
--
-- CLAUDE.md 17번 "규칙 기반 세그먼트를 먼저 만든다" 원칙에 따라 규칙 기반으로
-- 구축. mart_customer_lifecycle의 8개 상태와 대부분 1:1 대응하되, '탐색_고객'
-- (전체의 87.97%로 지나치게 큼)만 CLAUDE.md 17번이 요구하는 "구매 직전
-- 탐색형" vs "저관여 탐색형"으로 세분화한다.
--
-- 세분화 기준 (데이터 기반): 탐색_고객 중 n_page_visit >= 10(해당 그룹의
-- p90) 이거나 n_search_query > 0(탐색_고객의 90%가 검색을 전혀 안 해
-- 검색 존재 자체가 이례적 신호)인 경우를 "구매 직전 탐색형"(고관여/고의도)
-- 으로 본다. 결과: 2,470,981명(12.60%)이 고관여로 분류됨 — 과도하게
-- 크지도 작지도 않은 규모(CLAUDE.md 17번 "과접촉 위험" 고려).
--
-- '구매_비활성_위험_고객'과 '비활성_고객'은 세그먼트 레벨에서는
-- '구매_비활성형' 하나로 합친다 — CLAUDE.md 17번이 세그먼트를 8개로
-- 명시했고, recency의 세밀한 구분은 이미 lifecycle에 남아있어 세그먼트
-- 레벨에서 또 나눌 필요가 없다(대시보드 Segment Explorer는 세그먼트를,
-- Lifecycle 페이지는 lifecycle을 보여주는 방식으로 역할 분리).
--
-- 입력: mart_customer_lifecycle, mart_customer_360
-- 출력: Phase 7 대시보드 Segment Explorer, Phase 6 모델 feature(세그먼트 자체를 baseline rule로도 사용)
CREATE OR REPLACE TABLE mart_customer_segment AS
SELECT
    l.client_id,
    l.lifecycle_stage,
    CASE
        WHEN l.lifecycle_stage = '탐색_고객'
             AND (m.n_page_visit >= 10 OR m.n_search_query > 0)
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
JOIN mart_customer_360 m ON l.client_id = m.client_id;
