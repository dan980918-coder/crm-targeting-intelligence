"""Streamlit 대시보드를 헤드리스로 띄워 주요 페이지 스크린샷을 저장한다.

전제: streamlit이 별도 프로세스로 http://localhost:8501 에서 실행 중이어야 함.
"""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
OUT_DIR = Path("reports/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("", "dashboard_home.png"),
    ("/Overview", "dashboard_overview.png"),
    ("/Funnel", "dashboard_funnel.png"),
    ("/Lifecycle", "dashboard_lifecycle.png"),
    ("/Segment_Explorer", "dashboard_segment_explorer.png"),
    ("/Targeting_Simulator", "dashboard_targeting_simulator.png"),
    ("/AI_CRM_Report", "dashboard_ai_crm_report.png"),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        for path, filename in PAGES:
            url = BASE_URL + path
            print(f"방문: {url}")
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2.5)  # streamlit 렌더링/차트 로딩 대기
            page.screenshot(path=str(OUT_DIR / filename), full_page=True)
            print(f"저장: {OUT_DIR / filename}")
        browser.close()


if __name__ == "__main__":
    main()
