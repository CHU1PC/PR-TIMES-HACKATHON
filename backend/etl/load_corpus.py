import math
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

import duckdb
import numpy as np
import psycopg
from loguru import logger
from pgvector.psycopg import register_vector
from sqlalchemy import Engine, create_engine, inspect, make_url, text

from app.db.models import Category, Corpus, CorpusMedia, MediaFrequency, MediaTotal, Place
from app.settings import DATA_DIR, settings

CORPUS = DATA_DIR / "corpus.parquet"
VECTORS = DATA_DIR / "corpus_vec.npy"
MEDIA = DATA_DIR / "corpus_media.parquet"
PLACES = DATA_DIR / "places.parquet"
CATEGORIES = DATA_DIR / "categories.parquet"

# スキーマは alembic が持つ。ここは空のテーブルに詰めるだけ
MIGRATE_HINT = "先に `uv run alembic upgrade head` を実行してください"

# 12.9万行 × 256次元を1行ずつ INSERT すると終わらないので COPY に流す。全件を一度にメモリへ載せない
FETCH_BATCH = 10_000
LOG_EVERY = 500_000

TABLES = (
    Corpus.__tablename__,
    CorpusMedia.__tablename__,
    MediaFrequency.__tablename__,
    MediaTotal.__tablename__,
    Place.__tablename__,
    Category.__tablename__,
)

# 埋め込みは corpus_vec.npy の行番号で対応するので, 並びは index.py の SELECT と必ず同じにする
SELECT_CORPUS = f"""
    SELECT company_id, release_id, title, coalesce(subtitle, ''), coalesce(body_head, ''), company_name,
           business_category_id, business_category_name, release_type_name,
           prefecture_id, prefecture_name, city_name,
           created_at::date, reach
    FROM read_parquet('{CORPUS}')
    ORDER BY company_id, release_id
"""

# SELECT_CORPUS の14列 + 投入時に足す2列。順序を崩すと COPY がずれる
CORPUS_COLUMNS = (
    "company_id",
    "release_id",
    "title",
    "subtitle",
    "body_head",
    "company_name",
    "business_category_id",
    "business_category_name",
    "release_type_name",
    "prefecture_id",
    "prefecture_name",
    "city_name",
    "published_on",
    "reach",
    "reach_score",
    "embedding",
)

SELECT_MAX_REACH = f"SELECT max(reach) FROM read_parquet('{CORPUS}')"

SELECT_MEDIA = f"SELECT company_id, release_id, new_site_name FROM read_parquet('{MEDIA}')"

# 数えるのは行数でなく事例数なので, 主キー単位で DISTINCT を取る
SELECT_MEDIA_FREQUENCY = f"""
    SELECT new_site_name, count(DISTINCT (company_id, release_id))
    FROM read_parquet('{MEDIA}')
    GROUP BY 1
"""

# media_frequency の分母。1行だけ入る
SELECT_MEDIA_TOTAL = f"SELECT count(DISTINCT (company_id, release_id)) FROM read_parquet('{MEDIA}')"

SELECT_PLACES = f"SELECT kind, name, prefecture_id FROM read_parquet('{PLACES}')"

# categories.parquet は cases 列も持つが, テーブル定義に無いので落とす
SELECT_CATEGORIES = f"SELECT business_category_id, business_category_name FROM read_parquet('{CATEGORIES}')"

# corpus 以外は埋め込みが要らないので, 同じ手順でまとめて流す
LOOKUPS = (
    (CorpusMedia.__tablename__, ("company_id", "release_id", "new_site_name"), SELECT_MEDIA),
    (MediaFrequency.__tablename__, ("new_site_name", "case_count"), SELECT_MEDIA_FREQUENCY),
    (MediaTotal.__tablename__, ("case_count",), SELECT_MEDIA_TOTAL),
    (Place.__tablename__, ("kind", "name", "prefecture_id"), SELECT_PLACES),
    (Category.__tablename__, ("business_category_id", "business_category_name"), SELECT_CATEGORIES),
)


def ensure_tables(engine: Engine) -> None:
    """投入先が migration 済みか確かめる。

    Args:
        engine: 投入先への同期エンジン。

    Raises:
        RuntimeError: テーブルが未作成のとき。
    """
    inspector = inspect(engine)
    missing = [t for t in TABLES if not inspector.has_table(t)]
    if missing:
        msg = f"テーブルが無い: {', '.join(missing)}。{MIGRATE_HINT}"
        raise RuntimeError(msg)


def fetch(con: duckdb.DuckDBPyConnection, sql: str) -> Iterator[tuple[Any, ...]]:
    """DuckDB の結果をバッチで取り出す。

    Args:
        con: DuckDB 接続。
        sql: 実行する SELECT 文。

    Yields:
        列順に並んだ1行。
    """
    con.execute(sql)
    while batch := con.fetchmany(FETCH_BATCH):
        yield from batch


def corpus_rows(con: duckdb.DuckDBPyConnection, vectors: np.ndarray, max_reach: int) -> Iterator[tuple[Any, ...]]:
    """コーパスの各行に reach_score と埋め込みを足す。

    Args:
        con: DuckDB 接続。
        vectors: corpus_vec.npy。行番号が SELECT_CORPUS の並びに対応する。
        max_reach: reach の最大値。

    Yields:
        CORPUS_COLUMNS の順に並んだ1行。
    """
    scale = math.log1p(max_reach)
    for position, row in enumerate(fetch(con, SELECT_CORPUS)):
        # SELECT_CORPUS の末尾が reach。毎クエリ再計算しないよう投入時にスコア化する
        yield (*row, math.log1p(row[-1]) / scale, vectors[position])


def copy_rows(pg: psycopg.Connection[Any], table: str, columns: Sequence[str], rows: Iterable[tuple[Any, ...]]) -> int:
    """COPY で1テーブルに流し込む。

    Args:
        pg: 投入先への psycopg 接続。
        table: 投入先テーブル。
        columns: 投入する列。行のタプルと同じ順。
        rows: 流し込む行。

    Returns:
        流し込んだ行数。
    """
    statement = f"COPY {table} ({', '.join(columns)}) FROM STDIN"
    done = 0
    with pg.cursor() as cur, cur.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)
            done += 1
            if done % LOG_EVERY == 0:
                logger.info("{:<16}{:>9,}行 …", table, done)
    logger.info("{:<16}{:>9,}行 投入", table, done)
    return done


def load(pg: psycopg.Connection[Any], vectors: np.ndarray) -> None:
    """各テーブルへ parquet を読みながら COPY する。

    Args:
        pg: 投入先への psycopg 接続。
        vectors: corpus_vec.npy。
    """
    register_vector(pg)
    with duckdb.connect() as con:
        max_reach = con.execute(SELECT_MAX_REACH).fetchone()[0]
        logger.info("reach 最大 {}", max_reach)
        copy_rows(pg, Corpus.__tablename__, CORPUS_COLUMNS, corpus_rows(con, vectors, max_reach))
        for table, columns, sql in LOOKUPS:
            copy_rows(pg, table, columns, fetch(con, sql))


def verify(engine: Engine, vectors: int) -> None:
    """各テーブルの件数を出し, コーパスと埋め込みの件数一致を確かめる。

    Args:
        engine: 投入先への同期エンジン。
        vectors: corpus_vec.npy の行数。

    Raises:
        ValueError: コーパスと埋め込みの件数が一致しないとき。
    """
    with engine.connect() as conn:
        counts = {table: conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in TABLES}
    for table, rows in counts.items():
        logger.info("{:<16}{:>9,}行", table, rows)

    corpus = counts[Corpus.__tablename__]
    if corpus != vectors:
        msg = f"corpus ({corpus:,}) と corpus_vec.npy ({vectors:,}) の件数が一致しない"
        raise ValueError(msg)


def main() -> None:
    """手元の parquet と npy を PostgreSQL(pgvector) に投入する。"""
    url = make_url(settings.DATABASE_URL.get_secret_value()).set(drivername="postgresql+psycopg")
    engine = create_engine(url.render_as_string(hide_password=False))
    ensure_tables(engine)

    vectors = np.load(VECTORS)
    logger.info("埋め込み {} ({:.0f}MB)", vectors.shape, VECTORS.stat().st_size / 1024 / 1024)

    # COPY は SQLAlchemy を通さないので生の psycopg 接続を借りる。commit しないと返却時に rollback される
    raw = engine.raw_connection()
    try:
        pg = raw.driver_connection
        # 何度実行しても同じ結果になるよう連番も戻す
        with pg.cursor() as cur:
            cur.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY")
        logger.info("TRUNCATE {}", ", ".join(TABLES))
        load(pg, vectors)
        raw.commit()
    finally:
        raw.close()

    verify(engine, len(vectors))


if __name__ == "__main__":
    main()
