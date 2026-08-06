"""Phase 9 - LLM 프롬프트 및 금지 표현 검사 (CLAUDE.md 28~29번)."""

from __future__ import annotations

import json

from src.llm.schemas import CRMReportInput

SYSTEM_PROMPT = """당신은 이커머스 CRM 담당자를 돕는 분석 보조자입니다.

절대 규칙:
1. 입력으로 주어진 숫자 외에 새로운 숫자를 만들어내지 마세요. 특정 수치를
   언급해야 한다면 반드시 입력에 있는 값만 사용하세요.
2. 매출 개선, 실제 이탈률 개선, 실제 캠페인 전환율 향상 등 "실제 비즈니스
   성과가 이미 발생했다"는 표현을 쓰지 마세요. 이 데이터는 과거 스냅샷
   기반 시뮬레이션이며 실제 캠페인을 집행하지 않았습니다.
3. 상품명이나 검색어를 임의로 해석하지 마세요(이 데이터셋에는 원문 텍스트가
   없습니다).
4. 인과관계를 단정하지 마세요("이렇게 하면 반드시 ~된다" 대신 "~할 가능성이
   있다", "~로 보인다" 같은 가설적 표현을 쓰세요).
5. 특정 고객을 부정적으로 단정하지 마세요.
6. 근거 없는 고객 심리를 추정하지 마세요.

당신의 역할은 정확히 두 가지입니다:
- recommended_actions: 주어진 사실(facts)에 근거한 CRM 액션 제안 (실행하라는
  지시가 아니라 "제안"이며, 실험 없이 효과를 단정하지 않음)
- testable_hypotheses: 실제 캠페인 실험(A/B 테스트 등)으로 검증해야 하는 가설

각 항목은 한국어로, 간결하게(1~2문장) 작성하세요. JSON 형식으로만 응답하세요:
{"recommended_actions": ["...", "..."], "testable_hypotheses": ["...", "..."]}
"""


FORBIDDEN_PHRASES = [
    "매출을 개선",
    "매출을 증가",
    "매출이 개선",
    "매출이 증가",
    "이탈률을 개선",
    "이탈률이 개선",
    "전환율을 향상",
    "전환율이 향상",
    "캠페인 효과를 검증",
    "실제로 이탈률",
    "ROI를 개선",
    "실제 매출",
]


def contains_forbidden_claim(text: str) -> str | None:
    """금지된 성과 표현이 있으면 해당 문구를 반환, 없으면 None."""
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            return phrase
    return None


def build_user_prompt(report_input: CRMReportInput) -> str:
    payload = {
        "period": f"{report_input.period_start} ~ {report_input.period_end}",
        "data_facts": [f.model_dump() for f in report_input.data_facts],
        "segment_facts": [s.model_dump() for s in report_input.segment_facts],
        "model_predictions": [m.model_dump() for m in report_input.model_predictions],
    }
    return (
        "다음은 SQL과 모델에서 이미 검증된 사실입니다. 이 사실에 근거해서만 "
        "recommended_actions와 testable_hypotheses를 작성하세요:\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
    )
