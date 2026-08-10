import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.dashboard.data import format_count, load_segment_profile, show_data_period_notice, with_exact_help

st.set_page_config(page_title="Segment Explorer", page_icon="🧩", layout="wide")
st.title("Segment Explorer")
show_data_period_notice()

st.markdown(
    "규칙 기반 세그먼트 9개입니다 (CLAUDE.md 17번 — 군집분석은 사용하지 않음, "
    "`docs/data_dictionary.md` mart_customer_segment 참고)."
)

df = load_segment_profile()

selected = st.selectbox("세그먼트 선택", df["segment"].tolist())
row = df[df["segment"] == selected].iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("고객 수", format_count(row['n']), help=with_exact_help(row['n']))
c2.metric("구매율", f"{row['buy_rate']*100:.1f}%")
c3.metric("평균 방문 횟수", f"{row['avg_visit']:.1f}")
c4.metric("평균 구매 횟수", f"{row['avg_purchases']:.2f}")

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**CRM 목적**: {row['crm_purpose']}")
    st.markdown(f"**추천 액션**: {row['recommended_action']}")
with col2:
    st.markdown(f"**접촉 우선순위**: {row['priority']}")
    st.markdown(f"**과접촉 위험**: {row['over_contact_risk']}")

st.markdown("---")
st.subheader("전체 세그먼트 비교")

fig = px.bar(
    df.sort_values("n", ascending=True), x="n", y="segment", orientation="h",
    labels={"n": "고객 수", "segment": "세그먼트"},
)
fig.update_layout(height=400)
st.plotly_chart(fig, use_container_width=True)

st.dataframe(
    df[["segment", "n", "buy_rate", "avg_visit", "avg_search", "avg_purchases",
        "crm_purpose", "priority", "over_contact_risk"]],
    use_container_width=True, hide_index=True,
)
