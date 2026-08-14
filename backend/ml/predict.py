from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import lightgbm as lgb
import numpy as np

# 推論はコーパスにも DB にも触らない。読むのは lgbm.txt 1本だけで, pandas も sklearn も要らない
from ml.features import MISSING_CATEGORY, build_matrix, has_presence
from ml.paths import DEPLOY_MODEL_PATH

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class PlanScorer:
    """予定1件を pv_score の予測値に変換する。"""

    booster: lgb.Booster

    @classmethod
    def load(cls, path: Path = DEPLOY_MODEL_PATH) -> PlanScorer:
        """保存済みの木を読む。

        Args:
            path: lgbm.txt のパス。

        Returns:
            読み込んだ PlanScorer。
        """
        return cls(booster=lgb.Booster(model_file=str(path)))

    def score_many(
        self,
        vectors: np.ndarray,
        titles: list[str],
        *,
        business_category_id: int | None = None,
        prefecture_id: int | None = None,
    ) -> list[float]:
        """複数の予定をまとめて採点する。

        Args:
            vectors: (件数, 256) の L2正規化済みベクトル。
            titles: vectors と同じ並びの予定タイトル。
            business_category_id: 顧客の業種。None なら欠損扱い。
            prefecture_id: 顧客の都道府県。None なら欠損扱い。

        Returns:
            0〜1 の予測 pv_score。
        """
        count = len(titles)
        category = np.full(count, business_category_id or MISSING_CATEGORY)
        prefecture = np.full(count, prefecture_id or MISSING_CATEGORY)
        presence = np.array([float(has_presence(t)) for t in titles], dtype=np.float32)
        matrix = build_matrix(np.asarray(vectors, dtype=np.float32).reshape(count, -1), category, prefecture, presence)
        # 木の外挿で 0〜1 をはみ出すことがある。順位は変わらないが表示側の前提を守る
        return np.clip(self.booster.predict(matrix), 0.0, 1.0).tolist()

    def score(
        self,
        vector: np.ndarray,
        title: str,
        *,
        business_category_id: int | None = None,
        prefecture_id: int | None = None,
    ) -> float:
        """予定を1件採点する。

        Args:
            vector: (256,) の L2正規化済みベクトル。
            title: 予定のタイトル。
            business_category_id: 顧客の業種。
            prefecture_id: 顧客の都道府県。

        Returns:
            0〜1 の予測 pv_score。
        """
        scores = self.score_many(
            vector.reshape(1, -1),
            [title],
            business_category_id=business_category_id,
            prefecture_id=prefecture_id,
        )
        return scores[0]
