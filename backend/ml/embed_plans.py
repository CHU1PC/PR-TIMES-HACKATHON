from __future__ import annotations

import os

import numpy as np
from openai import OpenAI

from ml.paths import ARTIFACT_DIR

# 受け入れテストの予定文。順位が常識に合うかを見るだけで, 学習には使わない
ACCEPTANCE_PLANS = (
    "熊本市中央区に新店舗をオープンします",
    "創業50周年を迎えます",
    "新年のご挨拶",
    "定例の社内会議",
    "地元の高校生と共同開発したお菓子の販売会",
    "年頭所感を発表します",
)

PLAN_VECTOR_PATH = ARTIFACT_DIR / "plan_vec.npy"

# app/llm/embeddings.py と同じモデル・次元。ずらすとコーパスと噛み合わない
MODEL = "text-embedding-3-small"
DIMENSIONS = 256


def normalize(vectors: np.ndarray) -> np.ndarray:
    """コサイン類似度を内積1回で出せるように L2 正規化する。

    Args:
        vectors: (件数, 次元) の配列。

    Returns:
        正規化済みの float32 配列。
    """
    norm = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.where(norm == 0, 1, norm)).astype(np.float32)


def main() -> None:
    """受け入れテスト文を埋め込んで artifacts に置く。既にあれば何もしない。

    Raises:
        RuntimeError: OPENAI_API_KEY が環境に無いとき。
    """
    if PLAN_VECTOR_PATH.exists():
        print(f"既にある {PLAN_VECTOR_PATH}")
        return

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        msg = "OPENAI_API_KEY が無い。.env から export して再実行する"
        raise RuntimeError(msg)

    response = OpenAI(api_key=key).embeddings.create(model=MODEL, input=list(ACCEPTANCE_PLANS), dimensions=DIMENSIONS)
    ordered = sorted(response.data, key=lambda item: item.index)
    vectors = normalize(np.asarray([item.embedding for item in ordered], dtype=np.float32))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(PLAN_VECTOR_PATH, vectors)
    print(f"書き出し {PLAN_VECTOR_PATH} {vectors.shape}")


if __name__ == "__main__":
    main()
