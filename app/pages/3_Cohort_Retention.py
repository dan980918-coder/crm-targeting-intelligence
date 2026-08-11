import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.dashboard.data import load_cohort_retention, show_data_period_notice
from src.dashboard.theme import inject_global_css, metric, themed_layout

st.set_page_config(page_title="Cohort & Retention", page_icon="📈", layout="wide")
inject_global_css()
st.title("코호트 & 리텐션")
show_data_period_notice()

st.markdown(
    "가입일이 없어 **첫 관측 구매 주차**를 코호트 기준으로 사용합니다 "
    "(CLAUDE.md 14번 고정 정의)."
)

df = load_cohort_retention()

show_censored = st.checkbox(
    "관측 종료로 검열된(우측 검열) 최근 코호트도 표시",
    value=False,
    help="체크 해제 시 라벨이 실제보다 낮게 나오는 최근 4개 코호트를 숨깁니다 "
         "(2022-11-14 이후, docs/decisions_pending_review.md 참고)",
)

plot_df = df if show_censored else df[~df["is_28d_window_censored"]]

c1, c2, c3, c4 = st.columns(4)
metric(c1, "ncohort", "코호트 수", f"{len(plot_df)}", help="첫 관측 구매 주차 기준")
metric(c2, "r7", "평균 7일 재구매율", f"{plot_df['repurchase_7d_rate'].mean()*100:.1f}%")
metric(c3, "r14", "평균 14일 재구매율", f"{plot_df['repurchase_14d_rate'].mean()*100:.1f}%")
metric(c4, "r28", "평균 28일 재구매율", f"{plot_df['repurchase_28d_rate'].mean()*100:.1f}%")

fig = go.Figure()
for col, name in [("repurchase_7d_rate", "7일"), ("repurchase_14d_rate", "14일"), ("repurchase_28d_rate", "28일")]:
    fig.add_trace(go.Scatter(x=plot_df["cohort_week"], y=plot_df[col] * 100, mode="lines+markers", name=f"{name} 재구매율"))
fig.update_layout(xaxis_title="코호트 주차 (첫 관측 구매 기준)", yaxis_title="재구매율 (%)")
themed_layout(fig, height=380)
st.plotly_chart(fig, use_container_width=True)

if not show_censored:
    st.caption(
        f"검열된 {len(df) - len(plot_df)}개 코호트(2022-11-14 이후, 관측 종료로 "
        "28일 재구매 창을 다 채우지 못함)를 숨겼습니다. 체크박스로 표시할 수 있으나, "
        "해당 구간의 값은 실제보다 낮게 나타남에 유의하세요."
    )

st.subheader("코호트 상세 데이터 (정확한 값)")
st.dataframe(
    df[["cohort_week", "n_customers_in_cohort", "repurchase_7d_rate", "repurchase_14d_rate",
        "repurchase_28d_rate", "avg_purchase_days", "avg_category_diversity",
        "is_7d_window_censored", "is_14d_window_censored", "is_28d_window_censored"]],
    use_container_width=True,
)
