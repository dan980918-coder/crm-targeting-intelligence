"""Phase 8 대시보드 데이터 파일 스모크 테스트 — 파일 존재·필수 컬럼 확인."""

from pathlib import Path

import pandas as pd

DASHBOARD_DIR = Path("data/dashboard")


def test_all_dashboard_files_exist():
    expected = [
        "overview_kpis.csv",
        "funnel_summary.csv",
        "cohort_retention.csv",
        "lifecycle_distribution.csv",
        "segment_profile.csv",
        "targeting_simulation.csv",
    ]
    for name in expected:
        assert (DASHBOARD_DIR / name).exists(), f"{name} 없음 — scripts/build_dashboard_data.py 실행 필요"


def test_overview_kpis_has_expected_metrics():
    df = pd.read_csv(DASHBOARD_DIR / "overview_kpis.csv")
    metrics = set(df["metric"])
    expected = {"total_customers", "buyers", "repeat_buyers", "cart_customers",
                "at_risk_customers", "inactive_customers", "recent_converters"}
    assert expected <= metrics


def test_lifecycle_distribution_has_8_stages():
    df = pd.read_csv(DASHBOARD_DIR / "lifecycle_distribution.csv")
    assert len(df) == 8
    assert abs(df["pct"].sum() - 100) < 0.01


def test_segment_profile_has_8_segments_with_crm_metadata():
    df = pd.read_csv(DASHBOARD_DIR / "segment_profile.csv")
    assert len(df) == 8
    for col in ["crm_purpose", "recommended_action", "priority", "over_contact_risk"]:
        assert df[col].notna().all(), f"{col}에 결측 존재 — SEGMENT_META 매핑 누락 의심"


def test_targeting_simulation_matches_phase7():
    df = pd.read_csv(DASHBOARD_DIR / "targeting_simulation.csv")
    assert len(df) == 72
