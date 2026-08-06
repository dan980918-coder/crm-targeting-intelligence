"""Phase 2 - sql/staging 아래 SQL 파일을 실행해 DuckDB 데이터베이스에 staging 뷰를 만든다.

CLAUDE.md 32번 디렉터리 구조의 `data/processed/crm.duckdb`를 사용한다.
staging 레이어는 VIEW로 생성해 원본 Parquet을 lazy하게 참조한다
(전체를 메모리에 올리지 않는다는 Phase 1 원칙 유지).
"""

from pathlib import Path

import duckdb
import yaml

CONFIG_PATH = Path("config/paths.yaml")


def main() -> None:
    with open(CONFIG_PATH) as f:
        paths = yaml.safe_load(f)

    db_path = Path(paths["database_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    staging_dir = Path(paths["sql_staging_dir"])
    sql_files = sorted(staging_dir.glob("*.sql"))

    con = duckdb.connect(str(db_path))
    for sql_file in sql_files:
        print(f"실행: {sql_file}")
        con.sql(sql_file.read_text())

    print("\n생성된 staging 뷰:")
    views = con.sql(
        "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'stg_%' ORDER BY table_name"
    ).fetchall()
    for (name,) in views:
        cnt = con.sql(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  - {name}: {cnt:,} rows")

    con.close()
    print(f"\nDatabase: {db_path}")


if __name__ == "__main__":
    main()
