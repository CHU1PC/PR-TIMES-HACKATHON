from __future__ import annotations

import asyncio
from statistics import median
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text

from app.db import session
from app.db.models import EMBEDDING_DIMENSIONS

if TYPE_CHECKING:
    import numpy as np

# 並べるのは pv_score だけ。regional_score は予定の種類にほぼ反応せず(実測 0.37〜0.57 に張り付き),
# 反応するのは「他県の県名を書いたか」だった。U1 は同じ予定に地名を足す**中**の比較で,
# ランキングは予定**どうし**の比較。問いが違うので regional は助言側(slots.py)に回す
NEIGHBORS = 20

# index.py と同じ加点幅。似ているかの判断は揃える
SAME_CATEGORY_BONUS = 0.04
SAME_PREFECTURE_BONUS = 0.04

# 県が分からないときの地元重み。全件の非ゼロ率(実測 0.7678)。どこにいるか分からなければ
# 地元紙も名指しできないので, PV 寄りに倒しておく
DEFAULT_REGIONAL_WEIGHT = 0.77

# **反響では加点しない。**加点すると, どの予定を渡しても届いた事例ばかりが近傍に来て
# 全部が高得点になり, 予定どうしの差が消える。反響で加点してよいのは「見せる事例」の方(index.py)
NEIGHBOR_SQL = text("""
    SELECT pv_score
    FROM corpus
    ORDER BY (1 - (embedding <=> CAST(:vector AS vector)))
             + :category_bonus * COALESCE((business_category_id = :business_category_id)::int, 0)
             + :prefecture_bonus * COALESCE((prefecture_id = :prefecture_id)::int, 0) DESC
    LIMIT :top_k
""").bindparams(bindparam("vector", type_=Vector(EMBEDDING_DIMENSIONS)))

WEIGHT_SQL = text("SELECT regional_weight FROM prefecture_weight WHERE prefecture_id = :prefecture_id")


async def regional_weight(prefecture_id: int | None) -> float:
    """その県で地元を推してよいかの重みを引く。

    Args:
        prefecture_id: 顧客の都道府県。None なら全国の既定値。

    Returns:
        0〜1 の重み。奈良0.26 / 東京0.18 のように地元紙が転載しない県では小さくなる。
    """
    if prefecture_id is None:
        return DEFAULT_REGIONAL_WEIGHT
    async with session() as db:
        found = (await db.execute(WEIGHT_SQL, {"prefecture_id": prefecture_id})).scalar_one_or_none()
    return found if found is not None else DEFAULT_REGIONAL_WEIGHT


async def plan_score(
    vector: np.ndarray,
    *,
    business_category_id: int | None = None,
    prefecture_id: int | None = None,
    top_k: int = NEIGHBORS,
) -> float | None:
    """予定に近い事例が実際どれだけ読まれたかを1つの数にする。

    Args:
        vector: L2正規化済みの予定のベクトル。
        business_category_id: 顧客の業種。None なら加点しない。
        prefecture_id: 顧客の都道府県。None なら加点しない。
        top_k: 見る近傍の数。

    Returns:
        0〜1 のスコア。近傍が引けなければ None。
    """
    params = {
        "vector": vector,
        "business_category_id": business_category_id,
        "prefecture_id": prefecture_id,
        "category_bonus": SAME_CATEGORY_BONUS,
        "prefecture_bonus": SAME_PREFECTURE_BONUS,
        "top_k": top_k,
    }
    async with session() as db:
        rows = (await db.execute(NEIGHBOR_SQL, params)).scalars().all()
    if not rows:
        return None

    # 平均だと1件の突出で順位が変わる。「限定」が平均2.89倍・中央値0.96倍だったのと同じ罠
    return median(rows)


async def score_texts(
    vectors: list[np.ndarray],
    *,
    business_category_id: int | None = None,
    prefecture_id: int | None = None,
) -> list[float | None]:
    """複数の予定をまとめて採点する。

    Args:
        vectors: 予定ごとの L2正規化済みベクトル。
        business_category_id: 顧客の業種。
        prefecture_id: 顧客の都道府県。

    Returns:
        vectors と同じ並びのスコア。
    """
    return await asyncio.gather(
        *(
            plan_score(vector, business_category_id=business_category_id, prefecture_id=prefecture_id)
            for vector in vectors
        )
    )
