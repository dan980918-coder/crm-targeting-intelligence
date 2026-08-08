import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.dashboard.data import show_data_period_notice

st.set_page_config(page_title="CRM Targeting Intelligence", page_icon="📊", layout="wide")

st.title("Customer Lifecycle & CRM Targeting Intelligence")

st.markdown(
    """
모든 고객에게 동일한 CRM 액션을 적용하는 대신, 고객의 탐색·장바구니·구매
행동을 이용해 **재활성화 대상**과 **구매 유도 대상**을 우선 선정하는
분석 시스템입니다.
"""
)

show_data_period_notice()

st.markdown("---")
st.markdown(
    """
### 페이지 안내

- **Overview**: 핵심 KPI와 퍼널 요약
- **Funnel**: 탐색→장바구니→구매 고객 단위 퍼널
- **Cohort & Retention**: 첫 관측 구매 주차 코호트별 재구매율
- **Lifecycle**: 고객 라이프사이클 8개 상태 분포
- **Segment Explorer**: CRM 세그먼트별 특성과 추천 액션
- **Targeting Simulator**: 접촉 비율별 모델 vs 규칙 기반 타기팅 비교
- **AI CRM Report**: SQL 집계 기반 Data Facts/Model Predictions + LLM이 생성한
  Recommended Actions/Testable Hypotheses (API 키 없으면 mock 백엔드로 동작)

왼쪽 사이드바에서 페이지를 선택하세요.
"""
)
