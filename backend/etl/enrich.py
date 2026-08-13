import asyncio
import gzip
import sys
import time
from pathlib import Path

import duckdb
import psycopg
from loguru import logger

from app.settings import DATA_DIR, SELF_MEDIA
from etl.db import connect

# 抽出対象は corpus.py が選んだ base。合流結果を corpus.parquet として書き直す
BASE = DATA_DIR / "corpus_base.parquet"
CORPUS = DATA_DIR / "corpus.parquet"
MEDIA = DATA_DIR / "corpus_media.parquet"
REGIONAL = DATA_DIR / "regional_media.parquet"
OUT = DATA_DIR / "raw"

# 対象は corpus.parquet の 12.9万件だけ。本文全件(15.3G文字)を引かずに済ませるための ID 指定
CHUNK = 2000
CONCURRENCY = 4
CHUNK_TIMEOUT = "150s"

# body は HTML。実測で先頭1000文字のうち58%がタグとCSS属性だったので, 多めに取って除去後に切る
BODY_RAW_CHARS = 2500
BODY_TEXT_CHARS = 1000

# タグを空白に置換 → 実体参照を除去 → 連続空白を畳む。この順でないとタグ間の語が繋がる
STRIP_HTML = """
    trim(regexp_replace(
        regexp_replace(
            regexp_replace({column}, '<[^>]*>', ' ', 'g'),
            '&[a-zA-Z]+;|&#[0-9]+;', ' ', 'g'
        ),
    '\\s+', ' ', 'g'))
"""

# (company_id, release_id) は release の主キー。JOIN にすると PK の索引が引ける
TEXT_SQL = """
    SELECT r.company_id, r.release_id,
           replace(coalesce(r.subtitle, ''), chr(10), ' ') AS subtitle,
           replace(left(coalesce(r.body, ''), {chars}), chr(10), ' ') AS body_raw
    FROM release r
    JOIN (VALUES {pairs}) AS t(company_id, release_id)
      ON r.company_id = t.company_id AND r.release_id = t.release_id
"""

# 媒体名は new_site_name(site_name は運営会社名)。転載元の PR TIMES 自身は除く
MEDIA_SQL = """
    SELECT DISTINCT w.company_id, w.release_id, w.new_site_name
    FROM webclipping_list w
    JOIN (VALUES {pairs}) AS t(company_id, release_id)
      ON w.company_id = t.company_id AND w.release_id = t.release_id
    WHERE w.new_site_name <> '{self_media}'
"""


def targets() -> list[tuple[int, int]]:
    """抽出対象の (company_id, release_id) を読む。

    Returns:
        company_id 順に並んだ主キーの一覧。
    """
    with duckdb.connect() as con:
        return con.execute(
            f"SELECT company_id, release_id FROM read_parquet('{BASE}') ORDER BY company_id, release_id"
        ).fetchall()


async def dump(conn: psycopg.AsyncConnection, sql: str, path: Path) -> int:
    """COPY の結果を gzip で書き出す。

    Args:
        conn: RDS 接続。
        sql: COPY で包む SELECT 文。
        path: 出力先。書き終えてから rename する。

    Returns:
        ヘッダを除いた行数。
    """
    tmp = path.with_suffix(path.suffix + ".part")
    rows = 0
    with gzip.open(tmp, "wt", encoding="utf-8", newline="") as f:
        async with conn.cursor() as cur, cur.copy(f"COPY ({sql}) TO STDOUT WITH (FORMAT CSV, HEADER)") as copy:
            async for block in copy:
                text = bytes(block).decode("utf-8")
                rows += text.count("\n")
                f.write(text)
    tmp.rename(path)
    return max(rows - 1, 0)


async def fetch_chunk(index: int, pairs: list[tuple[int, int]], kinds: list[str], sem: asyncio.Semaphore) -> None:
    """1チャンク分の本文と媒体名を取る。既に出力があれば飛ばす。

    Args:
        index: チャンク番号。出力ファイル名になる。
        pairs: このチャンクの主キー。
        kinds: "text" と "media" のうち実行するもの。
        sem: 同時実行数を絞るセマフォ。
    """
    # 先頭だけ型を明示して JOIN の型を揃える
    head, *rest = pairs
    values = ", ".join([f"({head[0]}::bigint, {head[1]}::bigint)", *(f"({c}, {r})" for c, r in rest)])
    plans = {
        "text": (TEXT_SQL.format(chars=BODY_RAW_CHARS, pairs=values), OUT / f"ctext_{index:04d}.csv.gz"),
        "media": (MEDIA_SQL.format(pairs=values, self_media=SELF_MEDIA), OUT / f"cmedia_{index:04d}.csv.gz"),
    }
    todo = [(kind, *plans[kind]) for kind in kinds if not plans[kind][1].exists()]
    if not todo:
        return

    async with sem:
        conn = await connect(CHUNK_TIMEOUT)
        try:
            for kind, sql, path in todo:
                started = time.perf_counter()
                rows = await dump(conn, sql, path)
                logger.info("{} #{:>3} {:>8,}行 {:>6.1f}s", kind, index, rows, time.perf_counter() - started)
        finally:
            await conn.close()


async def extract(kinds: list[str]) -> None:
    """全チャンクを並行に取る。1チャンクの失敗で全体を止めない。

    Args:
        kinds: "text" と "media" のうち実行するもの。
    """
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = targets()
    chunks = [(i // CHUNK, pairs[i : i + CHUNK]) for i in range(0, len(pairs), CHUNK)]
    logger.info("対象 {:,}件 / {}チャンク / {}", len(pairs), len(chunks), kinds)

    sem = asyncio.Semaphore(CONCURRENCY)

    async def guarded(index: int, chunk: list[tuple[int, int]]) -> None:
        try:
            await fetch_chunk(index, chunk, kinds, sem)
        except (psycopg.Error, OSError) as e:
            logger.error("失敗 chunk={} err={}", index, e)

    started = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        for index, chunk in chunks:
            tg.create_task(guarded(index, chunk))
    logger.info("抽出完了 {:.1f}分", (time.perf_counter() - started) / 60)


def merge() -> None:
    """抽出した本文と媒体名を base に合流させ, 検索対象の corpus.parquet を作り直す。"""
    text_glob = OUT / "ctext_*.csv.gz"
    media_glob = OUT / "cmedia_*.csv.gz"

    with duckdb.connect() as con:
        stripped = STRIP_HTML.format(column="coalesce(t.body_raw, '')")
        con.execute(f"""
            COPY (
                SELECT b.*,
                       coalesce(t.subtitle, '') AS subtitle,
                       left({stripped}, {BODY_TEXT_CHARS}) AS body_head
                FROM read_parquet('{BASE}') b
                LEFT JOIN read_csv_auto('{text_glob}', union_by_name = true) t
                  USING (company_id, release_id)
                ORDER BY b.company_id, b.release_id
            ) TO '{CORPUS}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        con.execute(f"""
            COPY (
                SELECT company_id, release_id, new_site_name
                FROM read_csv_auto('{media_glob}', union_by_name = true)
            ) TO '{MEDIA}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        # 都道府県ごとに「その地域のリリースを拾っている媒体」を数える。
        # 事例が拾われた媒体をそのまま出すと, 熊本の顧客に埼玉の経済新聞が出てしまう
        con.execute(f"""
            COPY (
                SELECT c.prefecture_id, c.prefecture_name, m.new_site_name,
                       count(*) AS cases,
                       count(*) / (SELECT count(*) FROM read_parquet('{CORPUS}')
                                   WHERE prefecture_id = c.prefecture_id)::double AS share
                FROM read_parquet('{CORPUS}') c
                JOIN read_parquet('{MEDIA}') m USING (company_id, release_id)
                WHERE c.prefecture_id IS NOT NULL
                GROUP BY 1, 2, 3
            ) TO '{REGIONAL}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)

        filled = con.execute(f"""
            SELECT count(*) FILTER (WHERE body_head <> ''), count(*) FROM read_parquet('{CORPUS}')
        """).fetchone()
        media = con.execute(f"""
            SELECT count(*), count(DISTINCT new_site_name) FROM read_parquet('{MEDIA}')
        """).fetchone()

    logger.info("本文 {:,}/{:,}件に充填 → {}", *filled, CORPUS.name)
    logger.info("媒体 {:,}行 / ユニーク {:,}媒体 → {}", *media, MEDIA.name)


async def main() -> None:
    """引数で指定されたステップを実行する。既に出力があるチャンクは飛ばす。"""
    steps = sys.argv[1:] or ["text", "media", "merge"]
    kinds = [k for k in ("text", "media") if k in steps]
    if kinds:
        await extract(kinds)
    if "merge" in steps:
        merge()


if __name__ == "__main__":
    asyncio.run(main())
