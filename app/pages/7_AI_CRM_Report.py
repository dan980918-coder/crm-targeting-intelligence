import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.dashboard.data import format_count, show_data_period_notice, with_exact_help
from src.llm.client import get_available_backend
from src.llm.data_loader import build_report_input
from src.llm.report_generator import generate_crm_report

st.set_page_config(page_title="AI CRM Report", page_icon="🤖", layout="wide")
st.title("AI CRM Report")
show_data_period_notice()

backend = get_available_backend()
if backend == "mock":
    st.warning(
        "⚠️ 현재 LLM API 키가 설정되어 있지 않아 **mock(모의) 백엔드**로 생성된 "
        "리포트입니다 — 실제 LLM이 문장을 생성한 것이 아니라, 세그먼트 메타데이터를 "
        "규칙적으로 재구성한 결정론적 대체 출력입니다. `.env`에 `ANTHROPIC_API_KEY` "
        "또는 `OPENAI_API_KEY`를 추가하면 자동으로 실제 LLM 호출로 전환됩니다."
    )
else:
    st.success(f"✅ 실제 LLM 백엔드({backend})로 생성된 리포트입니다.")

contact_rate = st.select_slider("Model Predictions 기준 접촉 비율", options=[5, 10, 20, 30], value=10)

report_input = build_report_input(contact_rate_pct=contact_rate)
output = generate_crm_report(report_input)

st.caption(f"생성 방식: {output.generated_by} | 기간: {output.period_start} ~ {output.period_end}")

st.subheader("1. Data Facts (SQL에서 확인된 사실)")
cols = st.columns(len(output.data_facts))
for col, fact in zip(cols, output.data_facts):
    col.metric(fact.label, f"{format_count(fact.value)}{fact.unit}",
               help=with_exact_help(fact.value))

st.subheader("2. Model Predictions (모델 예측 결과)")
for m in output.model_predictions:
    st.markdown(
        f"- **{m.model_name}** ({m.label}), 상위 {m.contact_rate_pct}%: "
        f"Recall {m.recall*100:.1f}%, Lift {m.lift:.2f}배, Precision {m.precision*100:.1f}%"
    )
if not output.model_predictions:
    st.caption("해당 접촉 비율의 모델 예측 결과가 없습니다.")

st.subheader("3. Recommended Actions (제안된 CRM 액션)")
for a in output.recommended_actions:
    st.markdown(f"- {a}")

st.subheader("4. Testable Hypotheses (실험으로 검증해야 하는 가설)")
for h in output.testable_hypotheses:
    st.markdown(f"- {h}")

st.markdown("---")
st.caption(
    "CLAUDE.md 29번 원칙: 입력에 없는 숫자 생성 금지, 매출/이탈률 개선 등 실제 성과 "
    "표현 금지, 상품명·검색어 임의 해석 금지, 인과관계 단정 금지. 위반 문구가 감지되면 "
    "리포트 생성 자체가 예외로 중단됩니다(`src/llm/report_generator.py`)."
)
