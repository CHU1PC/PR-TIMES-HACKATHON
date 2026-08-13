import asyncio
import gzip
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import psycopg
from loguru import logger

from app.settings import DATA_DIR
from etl.db import connect

OUT = DATA_DIR / "raw"

# 実測: company_id 幅2000 で約86秒。150s に余裕を持たせ, 超えたチャンクは半分に割って収める
CHUNK_TIMEOUT = "150s"

# 幅1 まで割れば必ず収まる。1社で超える場合はその社だけが極端に転載が多い
MIN_WIDTH = 1

# company.company_id の実測レンジは 65〜188,338。上限に余裕を持たせる
COMPANY_MAX = 190_000
INITIAL_WIDTH = 2000

# RDS の接続数を食い潰さない範囲で同時実行を絞る
CONCURRENCY = 4

WC_SQL = """
    SELECT company_id, release_id,
           count(*) AS wc_rows,
           count(DISTINCT new_site_name) AS wc_uniq,
           count(DISTINCT new_site_name) FILTER (WHERE new_site_name <> 'PR TIMES') AS wc_uniq_ex,
           min(insert_date) AS first_clip,
           max(insert_date) AS last_clip
    FROM webclipping_list
    WHERE company_id >= {lo} AND company_id < {hi}
    GROUP BY company_id, release_id
"""

# body 本文は転送せず長さだけサーバ側で計算する(requirements §8.5)
RELEASE_SQL = """
    SELECT company_id, release_id, release_type_id, created_at, title,
           length(body) AS body_len,
           length(subtitle) AS subtitle_len,
           (subtitle <> '') AS has_subtitle,
           (lead_paragraph <> '') AS has_lead,
           (main_image <> '') AS has_image,
           (youtube_url <> '') AS has_youtube
    FROM release
    WHERE created_at >= '{year}-01-01' AND created_at < '{next_year}-01-01'
"""

SIMPLE_SQL = {
    "release_stat": "SELECT company_id, release_id, page_view, unique_user, like_count FROM release_statistic",
    "release_location": (
        "SELECT company_id, release_id, prefecture_id, city_id, location_category_id FROM release_location"
    ),
    "release_category": (
        "SELECT company_id, release_id, business_category_id, main_flg "
        "FROM release_business_category WHERE main_flg = 1"
    ),
    "company": "SELECT company_id, company_name, industry_id, ipo_type_id, capital, foundation_date FROM company",
    "release_type": "SELECT * FROM release_type",
    "business_category": "SELECT * FROM business_category",
    "industry": "SELECT * FROM industry",
    "prefecture": "SELECT * FROM prefecture",
    "city": "SELECT * FROM city",
    "location_category": "SELECT * FROM location_category",
}


async def dump(conn: psycopg.AsyncConnection, sql: str, path: Path) -> int:
    """COPY の結果を gzip で書き出す。

    Args:
        conn: RDS 接続。
        sql: COPY で包む SELECT 文。
        path: 出力先。書き終えてから rename するので中断してもゴミが残らない。

    Returns:
        ヘッダを除いた行数。
    """
    tmp = path.with_suffix(path.suffix + ".part")
    rows = 0
    # gzip 圧縮は同期だが, 支配的なのはサーバ側の集約待ちなのでループを止める時間は無視できる
    with gzip.open(tmp, "wt", encoding="utf-8", newline="") as f:
        async with conn.cursor() as cur, cur.copy(f"COPY ({sql}) TO STDOUT WITH (FORMAT CSV, HEADER)") as copy:
            async for block in copy:
                text = bytes(block).decode("utf-8")
                rows += text.count("\n")
                f.write(text)
    tmp.rename(path)
    return max(rows - 1, 0)


async def _run(sql: str, path: Path, label: str) -> None:
    """1本の抽出を実行して所要時間を記録する。

    Args:
        sql: 実行する SELECT 文。
        path: 出力先。
        label: ログに出す名前。
    """
    conn = await connect(CHUNK_TIMEOUT)
    try:
        started = time.perf_counter()
        rows = await dump(conn, sql, path)
        logger.info("{} {:>10,}行 {:>6.1f}s", label, rows, time.perf_counter() - started)
    finally:
        await conn.close()


async def wc_chunk(lo: int, hi: int, sem: asyncio.Semaphore) -> None:
    """1レンジ分の転載を集約する。タイムアウトしたら半分に割って再帰する。

    Args:
        lo: company_id の下限(含む)。
        hi: company_id の上限(含まない)。
        sem: 同時実行数を絞るセマフォ。再帰前に必ず解放される。
    """
    path = OUT / f"wc_{lo:07d}_{hi:07d}.csv.gz"
    # with_suffix は .gz だけを置換して .csv.split になるので, 名前を明示して組み立てる
    split_marker = OUT / f"wc_{lo:07d}_{hi:07d}.split"
    if path.exists():
        return
    width = hi - lo
    if not split_marker.exists():
        try:
            async with sem:
                await _run(WC_SQL.format(lo=lo, hi=hi), path, f"wc [{lo:>7,}-{hi:>7,})")
        except psycopg.errors.QueryCanceled:
            path.with_suffix(path.suffix + ".part").unlink(missing_ok=True)
            if width <= MIN_WIDTH:
                logger.error("wc [{}-{}) 幅1でもタイムアウト。この企業だけ個別に長い timeout で流す", lo, hi)
                return
            # 再実行時にこのレンジを 150 秒かけて再びタイムアウトさせないための印
            split_marker.touch()
            logger.warning("wc [{:,}-{:,}) タイムアウト → 分割", lo, hi)
        else:
            return
    mid = lo + width // 2
    await wc_chunk(lo, mid, sem)
    await wc_chunk(mid, hi, sem)


async def release_year(year: int, sem: asyncio.Semaphore) -> None:
    """1年分のリリースを抽出する。

    Args:
        year: 対象年。
        sem: 同時実行数を絞るセマフォ。
    """
    path = OUT / f"release_{year}.csv.gz"
    if path.exists():
        return
    async with sem:
        await _run(RELEASE_SQL.format(year=year, next_year=year + 1), path, f"release {year}")


async def simple_table(name: str, sem: asyncio.Semaphore) -> None:
    """分割不要な中小テーブルをそのまま抽出する。

    Args:
        name: SIMPLE_SQL のキー。
        sem: 同時実行数を絞るセマフォ。
    """
    path = OUT / f"{name}.csv.gz"
    if path.exists():
        return
    async with sem:
        await _run(SIMPLE_SQL[name], path, f"{name:<20}")


async def gather_bounded[T](fn: Callable[[T, asyncio.Semaphore], Awaitable[None]], items: list[T]) -> None:
    """同種のタスクを TaskGroup で並行実行する。1件の失敗で全体を止めない。

    Args:
        fn: 1件を処理するコルーチン。
        items: 処理対象。
    """
    sem = asyncio.Semaphore(CONCURRENCY)

    async def guarded(item: T) -> None:
        try:
            await fn(item, sem)
        except (psycopg.Error, OSError) as e:  # 1チャンクの失敗で残りを巻き添えにしない
            logger.error("失敗 item={} err={}", item, e)

    async with asyncio.TaskGroup() as tg:
        for item in items:
            tg.create_task(guarded(item))


async def main() -> None:
    """引数で指定されたステップを実行する。既に出力があるチャンクは飛ばす。"""
    OUT.mkdir(parents=True, exist_ok=True)
    steps = sys.argv[1:] or ["simple", "release", "wc"]
    started = time.perf_counter()

    if "simple" in steps:
        await gather_bounded(simple_table, list(SIMPLE_SQL))
    if "release" in steps:
        await gather_bounded(release_year, list(range(2005, 2027)))
    if "wc" in steps:
        ranges = [(lo, min(lo + INITIAL_WIDTH, COMPANY_MAX)) for lo in range(0, COMPANY_MAX, INITIAL_WIDTH)]
        await gather_bounded(lambda r, sem: wc_chunk(r[0], r[1], sem), ranges)

    logger.info("完了 {:.1f}分", (time.perf_counter() - started) / 60)


if __name__ == "__main__":
    asyncio.run(main())
