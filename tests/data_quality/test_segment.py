"""Phase 4 mart_customer_segment 데이터 품질 테스트."""

from pathlib import Path

import duckdb
import pytest
import yaml

CONFIG_PATH = Path("config/paths.yaml")


@pytest.fixture(scope="module")
def con():
    with open(CONFIG_PATH) as f:
        paths = yaml.safe_load(f)
    connection = duckdb.connect(str(paths["database_path"]), read_only=True)
    yield connection
    connection.close()


def test_pk_uniqueness_and_total(con):
    total = con.sql("SELECT COUNT(*) FROM mart_customer_segment").fetchone()[0]
    distinct = con.sql("SELECT COUNT(DISTINCT client_id) FROM mart_customer_segment").fetchone()[0]
    assert total == distinct == 22_298_361


def test_no_unclassified(con):
    n = con.sql("SELECT COUNT(*) FROM mart_customer_segment WHERE segment = '기타'").fetchone()[0]
    assert n == 0


def test_exactly_8_segments(con):
    n = con.sql("SELECT COUNT(DISTINCT segment) FROM mart_customer_segment").fetchone()[0]
    assert n == 8


def test_segment_consistent_with_lifecycle(con):
    # 구매 관련 세그먼트(비활성형 제외) 인원 합이 lifecycle의 해당 상태 인원과 일치해야 함
    checks = [
        ("첫_관측_구매_고관여형", "첫_관측_구매_고객"),
        ("안정적_반복구매형", "활성_구매_고객"),
        ("반복구매_감소형", "구매_감소_고객"),
        ("복귀형", "복귀_고객"),
        ("장바구니_이탈형", "장바구니_고객"),
    ]
    for seg, stage in checks:
        n_seg = con.sql(f"SELECT COUNT(*) FROM mart_customer_segment WHERE segment = '{seg}'").fetchone()[0]
        n_stage = con.sql(f"SELECT COUNT(*) FROM mart_customer_lifecycle WHERE lifecycle_stage = '{stage}'").fetchone()[0]
        assert n_seg == n_stage, f"{seg} 세그먼트({n_seg})가 {stage} 상태({n_stage})와 인원 불일치"


def test_inactive_segment_equals_merged_lifecycle_states(con):
    n_seg = con.sql("SELECT COUNT(*) FROM mart_customer_segment WHERE segment = '구매_비활성형'").fetchone()[0]
    n_stage = con.sql(
        "SELECT COUNT(*) FROM mart_customer_lifecycle WHERE lifecycle_stage IN ('구매_비활성_위험_고객', '비활성_고객')"
    ).fetchone()[0]
    assert n_seg == n_stage
