import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.dashboard.data import (
    load_overview_kpis,
    load_segment_profile,
    load_targeting_simulation,
    show_data_period_notice,
)

st.set_page_config(page_title="AI CRM Report", page_icon="🤖", layout="wide")
st.title("AI CRM Report")
show_data_period_notice()

st.warning(
    "⚠️ 이 페이지는 **Phase 9(LLM CRM 리포트) 미착수 상태의 자리표시자(scaffold)**"
    "입니다. 'Data Facts'와 'Model Predictions'는 실제 SQL/모델 결과이지만, "
    "'Recommended Actions'와 'Testable Hypotheses'는 아직 LLM이 생성하지 않았습니다 — "
    "Phase 9에서 CLAUDE.md 27번 파이프라인(DuckDB SQL → Python 검증 → Pydantic JSON → LLM)을 "
    "연결할 예정입니다."
)

kpis = load_overview_kpis()
seg_df = load_segment_profile()
sim_df = load_targeting_simulation()

st.subheader("1. Data Facts (SQL에서 확인된 사실)")
c1, c2, c3 = st.columns(3)
c1.metric("전체 관측 고객", f"{kpis['total_customers']:,.0f}")
c2.metric("구매 비활성 위험 고객", f"{kpis['at_risk_customers']:,.0f}")
c3.metric("장바구니 이탈형 세그먼트", f"{seg_df[seg_df['segment']=='장바구니_이탈형']['n'].iloc[0]:,.0f}")
st.caption("관측 기간: 2022-06-23 ~ 2022-12-08 (167일). 근거: reports/phase1_data_profile.md")

st.subheader("2. Model Predictions (모델 예측 결과)")
best_b = sim_df[
    (sim_df["model"] == "Model_B_propensity")
    & (sim_df["policy"] == "모델_LightGBM")
    & (sim_df["contact_rate_pct"] == 10)
]
if not best_b.empty:
    st.markdown(
        f"- Model B(구매성향, will_purchase_14d) LightGBM, 상위 10% 접촉 시 "
        f"Recall {best_b.iloc[0]['recall']*100:.1f}%, Lift {best_b.iloc[0]['lift']:.2f}배 "
        f"(테스트셋, out-of-sample). 근거: reports/phase6_modeling_results.md"
    )
best_a = sim_df[
    (sim_df["model"] == "Model_A_churn")
    & (sim_df["policy"] == "모델_LightGBM")
    & (sim_df["contact_rate_pct"] == 10)
]
if not best_a.empty:
    st.markdown(
        f"- Model A(구매 비활성, churn_14d) LightGBM, 상위 10% 접촉 시 "
        f"Recall {best_a.iloc[0]['recall']*100:.1f}%, Lift {best_a.iloc[0]['lift']:.2f}배"
    )

st.subheader("3. Recommended Actions (LLM이 제안한 CRM 액션)")
st.info("Phase 9 미착수 — LLM 연동 예정. 현재는 Phase 4 세그먼트 프로필의 규칙 기반 제안만 존재합니다 (Segment Explorer 페이지 참고).")

st.subheader("4. Testable Hypotheses (실험으로 검증해야 하는 가설)")
st.info("Phase 9 미착수 — LLM 연동 예정.")

st.markdown("---")
st.caption(
    "CLAUDE.md 29번 LLM 금지사항 준수 예정: 입력에 없는 숫자 생성 금지, "
    "매출 개선 수치 생성 금지, 실제 캠페인 성과처럼 표현 금지 등."
)
