from __future__ import annotations

import numpy as np

# app/ranking/score.py と同じ設定。比較の条件を揃えるため値をここに写す
NEIGHBORS = 20
SAME_CATEGORY_BONUS = 0.04
SAME_PREFECTURE_BONUS = 0.04

# 1度に持つ類似度行列の行数。全件を一度に取ると 26,000 x 103,000 で 10GB になる
QUERY_CHUNK = 1024


def knn_scores(
    query_vectors: np.ndarray,
    query_category: np.ndarray,
    query_prefecture: np.ndarray,
    corpus_vectors: np.ndarray,
    corpus_category: np.ndarray,
    corpus_prefecture: np.ndarray,
    corpus_pv_score: np.ndarray,
    top_k: int = NEIGHBORS,
) -> np.ndarray:
    """k-NN ベースラインを DB 抜きで再現する。近傍の pv_score の中央値を返す。

    Args:
        query_vectors: 採点する側の L2正規化済みベクトル。
        query_category: 採点する側の業種ID。
        query_prefecture: 採点する側の都道府県ID。
        corpus_vectors: 近傍を引くコーパスの L2正規化済みベクトル。
        corpus_category: コーパスの業種ID。
        corpus_prefecture: コーパスの都道府県ID。
        corpus_pv_score: コーパスの pv_score。
        top_k: 見る近傍の数。

    Returns:
        query_vectors と同じ並びのスコア。
    """
    scores = np.empty(len(query_vectors), dtype=np.float64)
    pool = np.ascontiguousarray(corpus_vectors, dtype=np.float32)

    for start in range(0, len(query_vectors), QUERY_CHUNK):
        stop = start + QUERY_CHUNK
        # ベクトルは L2正規化済みなので内積がそのままコサイン類似度
        similarity = query_vectors[start:stop] @ pool.T
        similarity += SAME_CATEGORY_BONUS * (query_category[start:stop, None] == corpus_category[None, :])
        similarity += SAME_PREFECTURE_BONUS * (query_prefecture[start:stop, None] == corpus_prefecture[None, :])
        neighbors = np.argpartition(-similarity, top_k, axis=1)[:, :top_k]
        # 平均だと1件の突出で順位が変わる。本番の score.py と同じく中央値
        scores[start:stop] = np.median(corpus_pv_score[neighbors], axis=1)

    return scores
