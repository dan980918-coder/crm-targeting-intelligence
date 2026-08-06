"""Phase 9 - LLM 호출 백엔드.

API 키가 없으면(이번 세션 기본 상태) mock 백엔드를 사용한다 — 실제 LLM이
아니라 이미 주어진 segment_facts/model_predictions 메타데이터를 규칙적으로
재구성한 결정론적(deterministic) 응답이며, generated_by="mock"으로 명확히
표시한다. 사용자가 나중에 .env에 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를
추가하면 자동으로 실제 API를 호출한다.
"""

from __future__ import annotations

import json
import os

from src.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from src.llm.schemas import CRMReportInput

DEFAULT_ANTHROPIC_MODEL = os.environ.get("CRM_LLM_MODEL", "claude-sonnet-5")
DEFAULT_OPENAI_MODEL = os.environ.get("CRM_LLM_MODEL_OPENAI", "gpt-4o-mini")


def get_available_backend() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "mock"


def _call_anthropic(report_input: CRMReportInput) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=DEFAULT_ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(report_input)}],
    )
    text = message.content[0].text
    return json.loads(text)


def _call_openai(report_input: CRMReportInput) -> dict:
    import openai

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=DEFAULT_OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(report_input)},
        ],
    )
    return json.loads(response.choices[0].message.content)


def _call_mock(report_input: CRMReportInput) -> dict:
    """API 키 없이도 파이프라인 전체를 시연·테스트할 수 있는 결정론적 대체
    구현. 주어진 사실을 넘어서는 새 숫자나 인과 주장을 만들지 않는다."""
    actions: list[str] = []
    hypotheses: list[str] = []

    if not report_input.segment_facts and not report_input.model_predictions:
        actions.append("입력된 세그먼트/모델 예측 데이터가 없어 구체적인 액션을 제안할 수 없습니다.")
        return {"recommended_actions": actions, "testable_hypotheses": hypotheses}

    for seg in report_input.segment_facts:
        actions.append(
            f"[{seg.segment}] (고객 {seg.n_customers:,}명, 접촉 우선순위 {seg.priority}) "
            f"목적: {seg.crm_purpose}에 맞는 CRM 액션을 검토해볼 수 있습니다."
        )
        hypotheses.append(
            f"[{seg.segment}] 세그먼트에 목적에 맞는 CRM 액션을 적용하면 반응률이 "
            "달라질 수 있다는 가설은 A/B 테스트로 검증이 필요합니다."
        )

    for pred in report_input.model_predictions:
        hypotheses.append(
            f"{pred.model_name}({pred.label}) 모델의 상위 {pred.contact_rate_pct}% 타겟팅이 "
            f"실제 캠페인에서도 시뮬레이션과 유사한 포착률을 보이는지는 실제 실험으로 "
            "확인이 필요합니다."
        )

    return {"recommended_actions": actions, "testable_hypotheses": hypotheses}


def call_llm(report_input: CRMReportInput) -> tuple[dict, str]:
    """반환값: (파싱된 응답 dict, 실제 사용된 backend 식별자)"""
    backend = get_available_backend()
    if backend == "anthropic":
        return _call_anthropic(report_input), DEFAULT_ANTHROPIC_MODEL
    if backend == "openai":
        return _call_openai(report_input), DEFAULT_OPENAI_MODEL
    return _call_mock(report_input), "mock"
