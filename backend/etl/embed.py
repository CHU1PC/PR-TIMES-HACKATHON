import asyncio
import time

import duckdb
import numpy as np
from loguru import logger
from openai import APIError, AsyncOpenAI, RateLimitError

from app.settings import DATA_DIR, settings

CORPUS = DATA_DIR / "corpus.parquet"
OUT = DATA_DIR / "corpus_vec.npy"

# バッチ単位で書き出す。1バッチの失敗で全件を捨てないための中間置き場（実測: 5分ぶんを失った）
SHARDS = DATA_DIR / "embed_shards"

# 1536次元は 129,045件で 793MB になりコンテナに載らない。256次元なら 132MB で精度低下も小さい
MODEL = "text-embedding-3-small"
DIMENSIONS = 256

# 1リクエストの入力上限は 300k トークン。本文冒頭込みで1件約1,086文字 = 概ね 1,000トークンなので
# 1000件では溢れる。日本語は1文字1トークンを超えることがあるため 200 件に落として余裕を持たせる
BATCH = 200

# 8 並列では継続的に 429 が返り, バッチが上限まで再試行して落ちた。4 に絞る
CONCURRENCY = 4

MAX_ATTEMPTS = 8
BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 60.0

# 埋め込みに使う列。RDS から subtitle / body_head を足した後も同じスクリプトで再実行できる
TEXT_COLUMNS = ("title", "subtitle", "body_head")

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())


def load_texts() -> tuple[list[str], int]:
    """コーパスを読み, 埋め込む文字列を組み立てる。並び順は corpus.parquet と同じ。

    Returns:
        埋め込む文字列と, 実際に使った列数。
    """
    with duckdb.connect() as con:
        described = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{CORPUS}')").fetchall()
        present = {row[0] for row in described}
        available = [c for c in TEXT_COLUMNS if c in present]
        cols = ", ".join(f"coalesce({c}, '')" for c in available)
        rows = con.execute(
            f"SELECT concat_ws(chr(10), {cols}) FROM read_parquet('{CORPUS}') ORDER BY company_id, release_id"
        ).fetchall()
    return [r[0] for r in rows], len(available)


async def embed_batch(texts: list[str], index: int) -> tuple[int, list[list[float]]]:
    """1バッチを埋め込む。レート制限は指数バックオフで待つ。

    Args:
        texts: 埋め込む文字列。
        index: 先頭の行番号。結果を元の順に戻すのに使う。

    Returns:
        先頭行番号と, ベクトルの並び。

    Raises:
        RuntimeError: 上限まで再試行しても成功しなかったとき。
    """
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = await client.embeddings.create(model=MODEL, input=texts, dimensions=DIMENSIONS)
        except (RateLimitError, APIError) as e:
            wait = min(BACKOFF_SECONDS * 2**attempt, MAX_BACKOFF_SECONDS)
            logger.warning("再試行 index={} attempt={} wait={:.0f}s err={}", index, attempt + 1, wait, type(e).__name__)
            await asyncio.sleep(wait)
        else:
            return index, [d.embedding for d in response.data]
    msg = f"index={index} のバッチが {MAX_ATTEMPTS} 回失敗した"
    raise RuntimeError(msg)


async def embed_all(texts: list[str]) -> np.ndarray:
    """全件を並行に埋め込み, L2正規化して返す。済んだバッチは再実行時に飛ばす。

    Args:
        texts: 埋め込む文字列。

    Returns:
        (件数, DIMENSIONS) の float32 配列。行の順序は入力と同じ。
    """
    SHARDS.mkdir(parents=True, exist_ok=True)
    offsets = list(range(0, len(texts), BATCH))
    todo = [i for i in offsets if not (SHARDS / f"{i:07d}.npy").exists()]
    logger.info("バッチ {}/{} 本を実行（残りは前回の続き）", len(todo), len(offsets))

    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0
    started = time.perf_counter()

    async def worker(index: int) -> None:
        nonlocal done
        async with sem:
            offset, batch = await embed_batch(texts[index : index + BATCH], index)
        np.save(SHARDS / f"{offset:07d}.npy", np.asarray(batch, dtype=np.float32))
        done += len(batch)
        logger.info("{:>7,}/{:,} {:.0f}s", done, len(todo) * BATCH, time.perf_counter() - started)

    async with asyncio.TaskGroup() as tg:
        for index in todo:
            tg.create_task(worker(index))

    vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
    for index in offsets:
        shard = np.load(SHARDS / f"{index:07d}.npy")
        vectors[index : index + len(shard)] = shard

    # コサイン類似度を内積1回で計算できるようにしておく
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


async def main() -> None:
    """corpus.parquet を埋め込んで corpus_vec.npy に書き出す。"""
    texts, columns = load_texts()
    logger.info("対象 {:,}件 / 使用列 {} / 平均 {:.0f}文字", len(texts), columns, sum(map(len, texts)) / len(texts))

    vectors = await embed_all(texts)
    np.save(OUT, vectors)
    logger.info("出力 {} {} ({:.0f}MB)", OUT, vectors.shape, OUT.stat().st_size / 1024 / 1024)

    # 組み上がったので中間ファイルは捨てる。残すと本文を変えたときに古いベクトルを拾う
    for shard in SHARDS.glob("*.npy"):
        shard.unlink()
    SHARDS.rmdir()


if __name__ == "__main__":
    asyncio.run(main())
