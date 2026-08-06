# Customer Lifecycle & CRM Targeting Intelligence

모든 고객에게 동일한 CRM 액션을 적용하는 대신, 고객의 탐색·장바구니·구매
행동을 이용해 **재활성화가 필요한 고객**과 **구매 유도가 필요한 고객**을
우선 선정하는 분석 시스템을 구축했다.

> ⚠️ 이 프로젝트는 실제 CRM 캠페인을 집행해 이탈률이나 매출을 직접 개선한
> 프로젝트가 아니다. 검증하는 것은 **"과거 행동 데이터를 이용한 대상 선정
> 효율"** 이며, 실제 캠페인 효과·매출 개선은 주장하지 않는다.

---

## 1. 문제 정의

이커머스 CRM에서 흔히 마주치는 질문:

- 제한된 CRM 접촉 자원(이메일/푸시 예산, 인력) 안에서 **누구에게 먼저
  연락해야 하는가?**
- 단순히 "최근 구매 안 한 사람"에게 다 연락하는 것보다, **모델 기반 선별이
  실제로 더 효율적인가?**
- 재활성화(구매 비활성 위험)와 구매 유도(신규/잠재 구매)는 **같은 방식으로
  타기팅해도 되는가?**

이 프로젝트는 실제 이커머스 고객 행동 로그를 이용해 위 질문에 데이터로
답한다.

## 2. 데이터 출처

- **데이터셋**: Synerise RecSys Challenge 2025 원본 데이터 (실제 온라인
  리테일 서비스의 익명화 고객 행동 로그)
- **공식 출처**: https://recsys.synerise.com/data-set
- **라이선스**: CC BY-NC 4.0 (© 2025 Synerise SA) — 원문: *"Universal
  Behavioral Modeling Dataset © 2025 by Synerise SA is licensed under
  Creative Commons Attribution-NonCommercial 4.0 International."*
- **이벤트 종류**: `product_buy`, `add_to_cart`, `remove_from_cart`,
  `page_visit`, `search_query`, `product_properties`
- **규모**: 고객 22,298,361명, 이벤트 226,758,312건 (구매 909,210건 포함)
- 원본 데이터는 라이선스상 이 저장소에 포함되지 않는다. 확보 절차는
  [`reports/phase1_download_log.md`](reports/phase1_download_log.md) 참고.

## 3. 데이터 한계

**데이터 관측 기간은 2022-06-23 ~ 2022-12-08(167일, 약 6개월)이며, 2023년
8월 이후 데이터는 0.0000%다.** 즉 이 프로젝트는 **최신 고객 행동이 아닌
2022년 하반기 특정 시점의 스냅샷**을 다룬다 (근거: `docs/methodology.md`
2026-08-05 정책 항목).

그 외 핵심 한계:

- **상품 단위 퍼널 불가**: `page_visit.url`이 `sku`와 연결되는 키가 없어,
  "이 상품을 본 고객이 이 상품을 샀는가"를 알 수 없다. 고객 단위 퍼널만 가능.
- **우측 검열(right-censoring)**: 구매자의 15.18%가 관측 종료 14일 이내
  마지막 구매를 기록해, 그 이후 재구매했는지 알 수 없다. 모델링 시
  `snapshot_date`를 관측 종료일 이전으로 제한해 원천 차단했다.
- **기록 없는 구매**: 구매자의 28.46%는 탐색·검색·장바구니 기록이 전혀
  없이 구매만 기록되어 있다 — 원인은 데이터로 확정할 수 없다.
- **"첫 구매"가 아닌 "첫 관측 구매"**: 가입일이 없어 첫 관측 구매를 기준으로
  코호트를 나눴으며, 진짜 첫 구매인지는 알 수 없다.

전체 한계 목록은 [`docs/limitations.md`](docs/limitations.md) 참고.

## 4. 전체 아키텍처

```
원본 Parquet (6개 이벤트 파일)
  → SQL staging (VIEW, 6개)
  → SQL intermediate (TABLE, 6개)
  → SQL mart (TABLE, 11개)
  → Feature/Label (mart_customer_snapshot)
  → 모델링 (LightGBM, Model A/B)
  → 타기팅 시뮬레이션 (mart_targeting_simulation)
  → Streamlit 대시보드 (7 페이지) / LLM CRM 리포트
```

상세 데이터 계보 다이어그램: [`docs/erd.md`](docs/erd.md)

## 5. SQL 데이터마트

DuckDB 기반, 3계층 구조.

| 계층 | 저장 방식 | 개수 |
|---|---|---:|
| staging | VIEW (lazy) | 6 |
| intermediate | TABLE | 6 |
| mart | TABLE | 11 |

전체 컬럼/Grain/PK 정의: [`docs/data_dictionary.md`](docs/data_dictionary.md)
빌드: `python3 scripts/build_database.py`

## 6. 고객분석

- **퍼널**: 탐색 98.66% → 장바구니 10.40% → 구매 2.59% (고객 단위, 상품
  단위는 불가능)
- **코호트/리텐션**: 첫 관측 구매 주차 기준 25개 코호트, 7일 재구매율
  ~10.9%, 14일 ~13.9%, 28일 ~18.1% (검열된 최근 코호트 제외)
- **라이프사이클**: 데이터 기반 recency 임계값(14/28/60일, 구매 간격
  중앙값·p90의 배수로 산출)으로 8개 상태 분류
- **세그먼트**: 규칙 기반 8개(군집분석 미사용), CRM 목적·추천 액션·접촉
  우선순위·과접촉 위험 포함

상세: [`reports/phase3_funnel_analysis.md`](reports/phase3_funnel_analysis.md),
[`reports/phase4_lifecycle_analysis.md`](reports/phase4_lifecycle_analysis.md),
[`reports/phase4_segment_profile.md`](reports/phase4_segment_profile.md)

## 7. 모델링

두 모델, 각각 14일/28일 라벨 비교, 시간순 Train(6)/Val(1)/Test(2) 스냅샷 분할.

| 모델 | 목적 | 모집단 | LightGBM AUC (test) | 최선 규칙 대비 |
|---|---|---|---:|---|
| Model A (구매 비활성) | 14/28일 내 미구매 예측 | 구매 이력 고객 | 0.753 / 0.741 | 규칙(최근성, 0.669)보다 우수 |
| Model B (구매성향) | 14/28일 내 구매 예측 | 활동 고객(비구매자 포함) | 0.867 / 0.860 | 규칙(최근성, 0.805)보다 우수 |

기준선(무작위/전체평균/최근성/빈도/라이프사이클) 대비 비교 포함. 상세:
[`reports/phase6_modeling_results.md`](reports/phase6_modeling_results.md),
모델 카드: [`reports/model_cards/`](reports/model_cards/)

## 8. 타기팅 시뮬레이션

테스트셋(out-of-sample) 기준, 동일 Recall 달성 시 최근성 규칙 대비 접촉
인원 절감률:

| 모델 | 절감률 (5~30% 접촉 구간) |
|---|---|
| Model A (구매 비활성) | 0.68% ~ 1.58% (제한적) |
| Model B (구매성향) | 18.47% ~ 45.94% (뚜렷함) |

> 상위 10% 고객을 모델로 선정했을 때, 단순 최근성 기준보다 동일한
> 포착률(Recall)을 20.47% 더 적은 인원으로 달성했다 (Model B, will_purchase_14d).

**왜 두 모델의 차이가 이렇게 큰가**: Lift는 라벨 기저율에 상한이 묶인다.
Model A의 라벨(90%+가 "비활성")은 이미 다수 클래스라 개선 여지가 작고,
Model B의 라벨(1~7%가 "구매함")은 소수 클래스라 모델의 순위 판별력이
그대로 실무 효율로 이어진다. 상세:
[`reports/phase7_targeting_simulation.md`](reports/phase7_targeting_simulation.md)

## 9. 대시보드

Streamlit 7페이지: Overview, Funnel, Cohort & Retention, Lifecycle, Segment
Explorer, Targeting Simulator, AI CRM Report.

```bash
python3 scripts/build_dashboard_data.py
streamlit run app/Home.py
```

모든 페이지에 데이터 관측 기간(2022년 6~12월) 고지를 표시하며, 우측 검열로
왜곡될 수 있는 지표(비활성 고객 수, 최근 코호트 재구매율)에는 별도 경고를
표시한다.

## 10. LLM 리포트

```
DuckDB SQL → Python 검증 → Pydantic JSON → LLM → CRM 리포트
```

LLM은 숫자를 계산하지 않는다 — Data Facts/Model Predictions는 Python이
계산한 값을 그대로 통과시키고, LLM은 Recommended Actions/Testable
Hypotheses만 생성한다. "매출 개선" 등 금지된 성과 표현이 출력에 감지되면
리포트 생성 자체가 예외로 중단된다.

API 키가 없으면 mock(결정론적 대체) 백엔드로 동작한다 — `.env`에
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`를 넣으면 코드 변경 없이 실제 LLM
호출로 전환된다. 상세: [`reports/phase9_llm_report_pipeline.md`](reports/phase9_llm_report_pipeline.md)

## 11. 핵심 결과

- 동일한 구매 후보 포착률(Recall)을 최근성 규칙 대비 **최대 45.94% 더 적은
  접촉 인원**으로 달성 (Model B, 20% 접촉 구간)
- 구매 비활성 위험 예측은 AUC 기준 규칙보다 통계적으로 우수(0.753 vs
  0.669)하나, 실무적 접촉 절감 효과는 제한적(라벨 기저율이 이미 90%+)
- 라이프사이클 임계값(14/28/60일)을 임의로 정하지 않고 실제 구매 간격
  분포(중앙값 9.48일, p90 68.05일)에서 데이터 기반으로 도출
- 우측 검열을 스냅샷 설계 단계에서 원천 차단해, 검열 미보정 시 발생했던
  "최근 코호트일수록 지표가 급락하는" 착시를 제거

## 12. 한계

전체 목록: [`docs/limitations.md`](docs/limitations.md). 핵심 요약은 위
"3. 데이터 한계" 참고.

## 13. 실제 운영 시 실험 설계 (제안, 미실행)

이 프로젝트는 실제 캠페인을 집행하지 않았다. 운영 적용을 고려한다면:

- **A/B 테스트**: 동일 접촉 예산에서 (A) 최근성 규칙 타기팅 vs (B) 모델
  기반 타기팅으로 대상을 나눠 실제 반응률(재구매/전환)을 비교
- **Model B 우선 검증**: 시뮬레이션상 개선 폭이 큰 구매성향 모델부터
  실제 실험 우선순위로 검토
- **재활성화 캠페인 비용 대비 효과 측정**: Model A는 시뮬레이션상 개선이
  작으므로, 실제 win-back 성공률이 규칙 기반과 통계적으로 유의미하게
  다른지부터 확인 필요
- **장기 관찰**: 6개월 스냅샷의 한계를 보완하기 위해, 최소 12개월 이상
  데이터로 재검증 권장

## 14. 실행 방법

상세 절차: [`docs/deployment.md`](docs/deployment.md)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 원본 데이터를 data/raw/synerise_dataset/에 위치시킨 후
python3 scripts/build_database.py
python3 scripts/train_model_a.py && python3 scripts/train_model_b.py
python3 scripts/build_targeting_simulation.py
python3 scripts/build_dashboard_data.py
streamlit run app/Home.py

pytest tests/ -q   # 112개 데이터 품질/모델/파이프라인 테스트
```

## 기술 스택

Python 3 · DuckDB · SQL · Parquet · pandas · scikit-learn · LightGBM ·
pytest · Streamlit · Plotly · Pydantic · (선택) Anthropic/OpenAI API

## 라이선스

코드: [MIT License](LICENSE). 데이터: CC BY-NC 4.0 (Synerise SA, 원본
미포함 — "2. 데이터 출처" 참고).
