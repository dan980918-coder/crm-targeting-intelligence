"""Phase 9 - CRM 리포트 생성 오케스트레이션 (CLAUDE.md 27번 파이프라인)."""

from __future__ import annotations

from src.llm.client import call_llm
from src.llm.prompts import contains_forbidden_claim
from src.llm.schemas import CRMReportInput, CRMReportOutput


class ForbiddenClaimError(RuntimeError):
    """LLM 출력에 금지된 성과 표현이 포함된 경우 발생 (CLAUDE.md 29번)."""


def generate_crm_report(report_input: CRMReportInput) -> CRMReportOutput:
    raw, generated_by = call_llm(report_input)

    recommended_actions = raw.get("recommended_actions", [])
    testable_hypotheses = raw.get("testable_hypotheses", [])

    for text in recommended_actions + testable_hypotheses:
        bad_phrase = contains_forbidden_claim(text)
        if bad_phrase:
            raise ForbiddenClaimError(
                f"LLM 출력에 금지된 성과 표현 발견: '{bad_phrase}' (문장: {text!r}). "
                "CLAUDE.md 29번 위반 — 리포트를 그대로 반환하지 않음."
            )

    return CRMReportOutput(
        period_start=report_input.period_start,
        period_end=report_input.period_end,
        data_facts=report_input.data_facts,  # passthrough — LLM이 재생성하지 않음
        model_predictions=report_input.model_predictions,  # passthrough
        recommended_actions=recommended_actions,
        testable_hypotheses=testable_hypotheses,
        generated_by=generated_by,
    )
