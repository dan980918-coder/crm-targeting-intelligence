import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.dashboard.data import format_count, load_funnel_summary, show_data_period_notice

st.set_page_config(page_title="Funnel", page_icon="🔻", layout="wide")
st.title("고객 단위 퍼널")
show_data_period_notice()

st.markdown(
    """
`page_visit.url`이 상품(sku)과 연결되는 키가 없어 **상품 단위 퍼널은
구조적으로 불가능**합니다 (Phase 1 8.9, `docs/methodology.md`). 아래는
고객 단위 탐색→장바구니→구매 퍼널입니다.
"""
)

funnel = load_funnel_summary()

fig = go.Figure(
    go.Funnel(
        y=["탐색", "장바구니 추가", "구매"],
        x=[funnel["explore"], funnel["cart"], funnel["buy"]],
        textinfo="value+percent initial+percent previous",
    )
)
fig.update_layout(height=450)
st.plotly_chart(fig, use_container_width=True)

st.subheader("구매자 경로 분해")
st.markdown(
    """
구매자가 항상 "탐색→장바구니→구매" 경로를 거치는 것은 아닙니다. 실제
경로별 분해는 다음과 같습니다 (Phase 3 퍼널 분석 참고).
"""
)

total_buy = funnel["buy"]
explore_cart_buy = funnel["cart_to_buy"]
no_footprint = funnel["buy_with_no_footprint"]

col1, col2 = st.columns(2)
col1.metric("탐색→장바구니→구매", format_count(explore_cart_buy),
            f"{explore_cart_buy/total_buy*100:.1f}%",
            help=f"정확한 값: {explore_cart_buy:,.0f}")
col2.metric("기록 없이 구매", format_count(no_footprint),
            f"{no_footprint/total_buy*100:.1f}%", delta_color="off",
            help=f"정확한 값: {no_footprint:,.0f}")

col3, col4 = st.columns(2)
col3.metric("탐색→장바구니 전환율", f"{funnel['explore_to_cart']/funnel['explore']*100:.2f}%")
col4.metric("장바구니→구매 전환율", f"{funnel['cart_to_buy']/funnel['cart']*100:.2f}%")

st.caption(
    "'기록 없이 구매' 고객은 탐색·검색·장바구니 이벤트가 전혀 없이 구매만 "
    "기록된 경우로, 데이터 로깅 범위 밖의 경로(앱 딥링크 등)일 가능성이 있습니다 "
    "— 원인은 데이터로 확정할 수 없습니다."
)
