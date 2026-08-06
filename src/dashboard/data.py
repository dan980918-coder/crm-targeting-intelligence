"""Streamlit 대시보드 데이터 로더. data/dashboard/의 사전 집계 파일만 읽는다."""

from pathlib import Path

import pandas as pd
import streamlit as st

DASHBOARD_DIR = Path("data/dashboard")

DATA_PERIOD_NOTICE = (
    "본 프로젝트는 2022년 6~12월 스냅샷 데이터를 사용하며, "
    "이는 최신 고객 행동이 아닌 특정 시점의 이커머스 행동 패턴 분석임을 명시합니다. "
    "(관측 기간: 2022-06-23 ~ 2022-12-08, 167일)"
)


@st.cache_data
def load_overview_kpis() -> dict:
    df = pd.read_csv(DASHBOARD_DIR / "overview_kpis.csv")
    return dict(zip(df["metric"], df["value"]))


@st.cache_data
def load_funnel_summary() -> dict:
    df = pd.read_csv(DASHBOARD_DIR / "funnel_summary.csv")
    return dict(zip(df["stage_metric"], df["value"]))


@st.cache_data
def load_cohort_retention() -> pd.DataFrame:
    df = pd.read_csv(DASHBOARD_DIR / "cohort_retention.csv", parse_dates=["cohort_week"])
    return df


@st.cache_data
def load_lifecycle_distribution() -> pd.DataFrame:
    return pd.read_csv(DASHBOARD_DIR / "lifecycle_distribution.csv")


@st.cache_data
def load_segment_profile() -> pd.DataFrame:
    return pd.read_csv(DASHBOARD_DIR / "segment_profile.csv")


@st.cache_data
def load_targeting_simulation() -> pd.DataFrame:
    return pd.read_csv(DASHBOARD_DIR / "targeting_simulation.csv")


def show_data_period_notice() -> None:
    st.info(f"ℹ️ {DATA_PERIOD_NOTICE}")
