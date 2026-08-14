import numpy as np
from openai import AsyncOpenAI

from app.settings import settings

# 1536次元は 12.9万件で 793MB になりコンテナに載らない。256次元なら 126MB
MODEL = "text-embedding-3-small"
DIMENSIONS = 256

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())


def normalize(vectors: np.ndarray) -> np.ndarray:
    """コサイン類似度を内積1回で出せるように L2 正規化する。

    Args:
        vectors: (件数, 次元) または (次元,) の配列。

    Returns:
        正規化済みの float32 配列。
    """
    axis = vectors.ndim - 1
    norm = np.linalg.norm(vectors, axis=axis, keepdims=True)
    return (vectors / np.where(norm == 0, 1, norm)).astype(np.float32)


async def embed(text: str) -> np.ndarray:
    """検索クエリを1本埋め込む。

    Args:
        text: 埋め込む文字列。

    Returns:
        正規化済みの (DIMENSIONS,) 配列。
    """
    response = await client.embeddings.create(model=MODEL, input=text, dimensions=DIMENSIONS)
    return normalize(np.asarray(response.data[0].embedding, dtype=np.float32))


async def embed_many(texts: list[str]) -> list[np.ndarray]:
    """複数をまとめて埋め込む。1ヶ月ぶんの予定を1リクエストで済ませる。

    Args:
        texts: 埋め込む文字列。空なら API を叩かない。

    Returns:
        texts と同じ並びの正規化済みベクトル。
    """
    if not texts:
        return []
    response = await client.embeddings.create(model=MODEL, input=texts, dimensions=DIMENSIONS)
    # data は index 順に返る保証が無いので並べ直す
    ordered = sorted(response.data, key=lambda item: item.index)
    return list(normalize(np.asarray([item.embedding for item in ordered], dtype=np.float32)))
