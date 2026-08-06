import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.dashboard.data import load_funnel_summary, load_overview_kpis, show_data_period_notice

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
st.title("CRM Overview")
show_data_period_notice()

kpis = load_overview_kpis()
funnel = load_funnel_summary()

st.subheader("핵심 KPI")
c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 관측 고객", f"{kpis['total_customers']:,.0f}")
c2.metric("구매 고객", f"{kpis['buyers']:,.0f}", help="관측 기간 내 1회 이상 구매")
c3.metric("반복구매 가능 고객", f"{kpis['repeat_buyers']:,.0f}", help="서로 다른 날짜에 2회 이상 구매")
c4.metric("장바구니 고객", f"{kpis['cart_customers']:,.0f}")

c5, c6, c7 = st.columns(3)
c5.metric("구매 비활성 위험 고객", f"{kpis['at_risk_customers']:,.0f}",
          help="마지막 구매 후 29~60일 경과 (docs/methodology.md 데이터 기반 임계값)")
c6.metric("비활성 고객", f"{kpis['inactive_customers']:,.0f}", help="마지막 구매 후 60일 초과 경과")
c7.metric("최근 14일 구매 전환(최신 스냅샷)", f"{kpis['recent_converters']:,.0f}",
          help="mart_purchase_propensity 최신 snapshot_date 기준 will_purchase_14d=1")

st.caption(
    "⚠️ '구매 비활성 위험/비활성' 고객 수는 관측 종료 시점 기준 단면입니다. "
    "이 중 일부는 실제 이탈이 아니라 우측 검열(관측 종료로 인한 데이터 절단) 효과일 수 있습니다 — "
    "자세한 내용은 docs/limitations.md 참고."
)

st.markdown("---")
st.subheader("핵심 퍼널 (고객 단위)")

fig = go.Figure(
    go.Funnel(
        y=["탐색", "장바구니 추가", "구매"],
        x=[funnel["explore"], funnel["cart"], funnel["buy"]],
        textinfo="value+percent initial",
    )
)
fig.update_layout(height=400)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"참고: 구매 고객 중 {funnel['buy_with_no_footprint']:,.0f}명"
    f"({funnel['buy_with_no_footprint']/funnel['buy']*100:.1f}%)은 탐색·장바구니 기록 없이 "
    "구매만 기록되어 있어 위 퍼널 경로를 거치지 않았습니다 (상품 단위 퍼널은 "
    "page_visit과 sku 연결 불가로 구조적으로 불가능 — Phase 3 참고)."
)
