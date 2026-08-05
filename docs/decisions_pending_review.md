# Decisions Pending Review — 전처리/정제 잠정 결정 로그

CLAUDE.md에 명시된 Phase 중단 조건(구조적 게이트)이 아닌, 전처리/정제 관련
재량 판단은 매번 멈춰 묻지 않고 합리적 기본값으로 처리한 뒤 이 문서에
기록한다. 사용자가 나중에 한 번에 검토하고 필요하면 수정을 지시할 수 있다.

각 항목 형식: 이슈 → 검토한 선택지 → 선택한 기본값과 근거 → 반영 위치(재현 가능하도록) → 상태

---

## 2026-08-05 (Phase 1, 8.6 이후) — 버스트 이벤트 (5초 이내 동일 고객·상품 반복)

**이슈**: `scripts/validate_event_quality.py` 결과, 동일 (client_id, sku/url)
조합이 5초 이내에 반복 기록되는 비율이 product_buy 16.44%(381,152건),
add_to_cart 4.72%, remove_from_cart 10.30%, page_visit 16.60%(33,118,828건),
search_query(client_id 기준) 13.03%로 확인됨 (`reports/phase1_data_quality.csv`
섹션 B). 원인(더블클릭 재로깅 / 수량별 개별 로깅 / 실제 재구매)은 세션ID나
주문ID가 데이터에 없어 완전히 확정할 수 없음.

**검토한 선택지**
1. 최초 1건만 남기고 즉시 dedup
2. 원본 보존 + 별도 플래그 컬럼 추가(비파괴적)
3. 원인 조사 먼저 완료 후 결정

**선택한 기본값**: **2번 (원본 보존 + 플래그 컬럼)**

**근거**: 원인이 불확실한 상태에서 삭제(1번)는 되돌릴 수 없고, product_buy처럼
매출과 직결된 테이블에서 실제 유효 행동(예: 같은 상품 2개를 짧은 간격으로
개별 구매)을 지울 위험이 있다. 조사(3번)는 order_id/session_id 부재로 완전한
결론에 도달하기 어려워 시간 대비 확신도가 낮다. 플래그 추가는 가역적이고
저위험이며, 이후 Phase 2에서 언제든 "포함/제외" 두 버전을 다 만들어볼 수 있다.

**반영 위치**: Phase 2 SQL staging 레이어(`sql/staging/stg_product_buy.sql` 등)
설계 시 `is_burst_repeat_5s` (또는 유사) boolean 컬럼을 추가해 원본 행은
유지하되 플래그로 구분하는 방식으로 구현 예정. Phase 1에서는 정의만 기록하고
실제 스키마 변경은 하지 않음(원본 파일 미변경, `data/raw/`는 read-only 취급).

**상태**: 잠정 결정 — 사용자 검토 대기 (Phase 2에서 실제 구현 시 재확인)

---

## 2026-08-05 (Phase 1, 8.6 이후) — 이상치 고객 (극단적 고빈도 client_id)

**이슈**: 고객별 이벤트 수 분포에서 극단적 long-tail 이상치 발견 (예:
page_visit p99.9=463인데 max=55,561, client_id OUTLIER_13). client_id `OUTLIER_07`,
`OUTLIER_06`, `OUTLIER_08`은 여러 이벤트 타입(add_to_cart, remove_from_cart,
search_query)에서 동시에 상위 이상치로 반복 등장 — 봇/크롤러 또는 비정상
파워유저 가능성 (`reports/phase1_event_quality.md` 섹션 A,
`reports/phase1_data_quality.csv`).

**검토한 선택지**
1. 8.7~8.9까지 그대로 두고 지켜보기 (배제하지 않음)
2. 지금 바로 제외 기준(예: p99.9 초과) 설정
3. 배제하지 않되 별도 "이상치 후보 리스트"로 추적

**선택한 기본값**: **1번 + 3번 결합** — 배제하지 않고 원본 그대로 유지하며,
이번에 발견된 이상치 client_id 후보를 별도 CSV로 기록해 추적한다. 이후
8.7~8.9 및 Phase 3~6 보고서에서 평균 대신 중앙값/percentile 중심으로
서술한다.

**근거**: CLAUDE.md 1~4번 규칙(데이터 확인 전 기준 임의 확정 금지)에 따라
원인(봇인지 정상 고빈도 고객인지)을 모른 채 배제 기준(2번)부터 정하는 것은
성급하다. 반대로 아무 기록 없이 방치하면 나중에 이 고객들의 존재를 잊고
평균 기반 지표를 그대로 신뢰할 위험이 있어, 후보 리스트로 남겨 추적성을
확보한다.

**반영 위치**: `reports/phase1_outlier_candidates.csv` 생성 (아래 표 참고).
이후 Phase 4(세그먼트 설계)·Phase 5~6(모델링 feature 처리)에서 이 목록을
참고해 클리핑/제외/별도 세그먼트 여부를 다시 판단한다.

| client_id | 등장 이벤트 타입(횟수) |
|---|---|
| OUTLIER_07 | add_to_cart(1,993), remove_from_cart(1,511), search_query(4,558) |
| OUTLIER_06 | add_to_cart(2,200), remove_from_cart(1,032) |
| OUTLIER_08 | add_to_cart(1,491), remove_from_cart(1,351) |
| OUTLIER_13 | page_visit(55,561) |
| OUTLIER_14 | page_visit(37,073) |
| OUTLIER_15 | page_visit(29,566) |
| OUTLIER_16 | page_visit(28,306) |
| OUTLIER_17 | page_visit(25,860) |
| OUTLIER_01 | product_buy(644) |
| OUTLIER_02 | product_buy(536) |
| OUTLIER_03 | product_buy(485) |
| OUTLIER_04 | product_buy(404) |
| OUTLIER_05 | product_buy(383) |
| OUTLIER_09 | add_to_cart(1,227) |
| OUTLIER_10 | add_to_cart(1,220) |
| OUTLIER_11 | remove_from_cart(858) |
| OUTLIER_12 | remove_from_cart(823) |
| OUTLIER_18 | search_query(3,245) |
| OUTLIER_19 | search_query(2,916) |
| OUTLIER_20 | search_query(2,824) |
| OUTLIER_21 | search_query(2,353) |

**상태**: 잠정 결정 — 사용자 검토 대기 (Phase 4~6에서 실제 처리 여부 재확인)

---

(이후 항목은 아래에 시간순으로 계속 추가한다.)
