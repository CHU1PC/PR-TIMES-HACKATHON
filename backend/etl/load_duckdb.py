import duckdb
from loguru import logger

from app.settings import DATA_DIR

RAW = DATA_DIR / "raw"
DB = DATA_DIR / "analysis.duckdb"

# 1テーブル = 1 glob。wc は分割チャンクが複数ファイルに散っているのでまとめて読む。
# release_* だと release_stat / release_location / release_category / release_type まで拾うので年で絞る
SOURCES = {
    "release": "release_2[0-9][0-9][0-9].csv.gz",
    "wc_agg": "wc_*.csv.gz",
    "release_stat": "release_stat.csv.gz",
    "release_location": "release_location.csv.gz",
    "release_category": "release_category.csv.gz",
    "company": "company.csv.gz",
    "release_type": "release_type.csv.gz",
    "business_category": "business_category.csv.gz",
    "industry": "industry.csv.gz",
    "prefecture": "prefecture.csv.gz",
    "city": "city.csv.gz",
    "location_category": "location_category.csv.gz",
}

# ETL の分割は company_id レンジなので, 同じ (company_id, release_id) が2ファイルに跨ることはない
UNIQUE_KEYS = {
    "release": ("company_id", "release_id"),
    "wc_agg": ("company_id", "release_id"),
    "release_stat": ("company_id", "release_id"),
}


def load(con: duckdb.DuckDBPyConnection, table: str, pattern: str) -> int:
    """CSV.gz を1テーブルに取り込む。

    Args:
        con: DuckDB 接続。
        table: 作成するテーブル名。
        pattern: data/raw 配下の glob。

    Returns:
        取り込んだ行数。
    """
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('{RAW / pattern}', union_by_name = true)")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def verify(con: duckdb.DuckDBPyConnection, table: str, keys: tuple[str, ...]) -> None:
    """主キーが重複していないか確かめる。

    Args:
        con: DuckDB 接続。
        table: 対象テーブル。
        keys: 一意であるべき列。

    Raises:
        ValueError: 重複があるとき。
    """
    cols = ", ".join(keys)
    sql = f"SELECT count(*) FROM (SELECT {cols} FROM {table} GROUP BY {cols} HAVING count(*) > 1)"
    dup = con.execute(sql).fetchone()[0]
    if dup:
        msg = f"{table} の ({cols}) に {dup:,} 件の重複があります"
        raise ValueError(msg)


def main() -> None:
    """data/raw の CSV.gz を analysis.duckdb にまとめる。"""
    DB.unlink(missing_ok=True)
    with duckdb.connect(str(DB)) as con:
        for table, pattern in SOURCES.items():
            rows = load(con, table, pattern)
            logger.info("{:<20}{:>12,}行", table, rows)

        for table, keys in UNIQUE_KEYS.items():
            verify(con, table, keys)
            logger.info("{:<20}主キー重複なし", table)

    logger.info("出力 {} ({:.0f}MB)", DB, DB.stat().st_size / 1024 / 1024)


if __name__ == "__main__":
    main()
