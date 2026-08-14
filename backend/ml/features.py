from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EMBEDDING_DIMENSIONS = 256

# 存在告知クラスタ。PV 勝率 72.0% / 中央値比 1.38倍。実拠点を持つ業種でだけ効くので,
# 業種と組み合わせて木に判断させる(EC・通販 50.7% / システム開発 50.9% では効かない)
PRESENCE_KEYWORDS = ("誕生", "オープン", "グランド", "リニューアル", "開設", "店舗", "ショップ", "拠点")

# タイトル長・記号・括弧・金額表記・サブタイトルの有無は実測で効かなかったため入れない。
# release_type_id は学習では効く(+0.011)が予定の時点では決まらないので, 推論の契約から外す
CATEGORY_FEATURES = ("business_category_id", "prefecture_id")
FEATURE_NAMES = [f"emb_{i}" for i in range(EMBEDDING_DIMENSIONS)] + [*CATEGORY_FEATURES, "presence"]

# 欠損の都道府県(実データで 15,763行)を入れる枠。実IDは 1〜47 / 業種は 1〜92 なので 0 は空く
MISSING_CATEGORY = 0


def has_presence(title: str) -> bool:
    """タイトルが存在告知クラスタの語を含むか。

    Args:
        title: 予定またはリリースのタイトル。

    Returns:
        含むなら True。
    """
    return any(keyword in title for keyword in PRESENCE_KEYWORDS)


def build_matrix(
    vectors: np.ndarray,
    business_category_id: np.ndarray,
    prefecture_id: np.ndarray,
    presence: np.ndarray,
) -> np.ndarray:
    """学習・推論で共通の特徴行列を組む。列順は FEATURE_NAMES と揃える。

    Args:
        vectors: L2正規化済みの (件数, 256) 埋め込み。
        business_category_id: 業種ID。欠損は MISSING_CATEGORY。
        prefecture_id: 都道府県ID。欠損は MISSING_CATEGORY。
        presence: 存在告知フラグ。

    Returns:
        (件数, 259) の float32 行列。
    """
    columns = (
        vectors.astype(np.float32),
        business_category_id.reshape(-1, 1).astype(np.float32),
        prefecture_id.reshape(-1, 1).astype(np.float32),
        presence.reshape(-1, 1).astype(np.float32),
    )
    return np.hstack(columns)


@dataclass(frozen=True)
class DenseEncoder:
    """線形モデルと MLP 用に, カテゴリIDを one-hot へ広げる。"""

    category_widths: tuple[int, ...]

    @classmethod
    def fit(cls, matrix: np.ndarray) -> DenseEncoder:
        """学習側に出てきたIDの幅を覚える。

        Args:
            matrix: build_matrix() の行列。

        Returns:
            幅を持った DenseEncoder。
        """
        offset = EMBEDDING_DIMENSIONS
        widths = tuple(int(matrix[:, offset + i].max()) + 1 for i in range(len(CATEGORY_FEATURES)))
        return cls(category_widths=widths)

    def transform(self, matrix: np.ndarray) -> np.ndarray:
        """カテゴリ列を one-hot に置き換える。未知IDは最大IDに丸める。

        Args:
            matrix: build_matrix() の行列。

        Returns:
            (件数, 256 + sum(幅) + 1) の float32 行列。
        """
        offset = EMBEDDING_DIMENSIONS
        blocks = [matrix[:, :offset]]
        for i, width in enumerate(self.category_widths):
            codes = np.clip(matrix[:, offset + i].astype(np.int32), 0, width - 1)
            blocks.append(np.eye(width, dtype=np.float32)[codes])
        blocks.append(matrix[:, offset + len(self.category_widths) :])
        return np.hstack(blocks)
