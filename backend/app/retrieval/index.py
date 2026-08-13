from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text

from app.db import session
from app.db.models import EMBEDDING_DIMENSIONS
from app.schema.proposal import ProposalCase

if TYPE_CHECKING:
    import numpy as np
    from sqlalchemy import Row

# ハードフィルタにしない。業種推定が外れると結果が丸ごと壊れるので, 類似度への加点に留める
SAME_CATEGORY_BONUS = 0.04
SAME_PREFECTURE_BONUS = 0.04

# 「似ている」だけでなく「実際に広く届いた」ものを上に出す。log を取るのは 395 media の外れ値に引きずられないため
REACH_BONUS = 0.05

# embedding は L2 正規化済みなので 1 - コサイン距離 が類似度。NULL は COALESCE で加点しない側に倒す。
# 加点式で並べる以上, 索引は効かず全件走査になる
SEARCH_SQL = text(f"""
    SELECT company_id, release_id, title, subtitle, body_head, company_name,
           business_category_name, release_type_name, prefecture_name, city_name,
           to_char(published_on, 'YYYY-MM-DD') AS published_on, reach,
           (1 - (embedding <=> CAST(:vector AS vector)))
             + {REACH_BONUS} * reach_score
             + {SAME_CATEGORY_BONUS} * COALESCE((business_category_id = :business_category_id)::int, 0)
             + {SAME_PREFECTURE_BONUS} * COALESCE((prefecture_id = :prefecture_id)::int, 0) AS score
    FROM corpus
    ORDER BY score DESC
    LIMIT :top_k
""").bindparams(bindparam("vector", type_=Vector(EMBEDDING_DIMENSIONS)))


def _case(row: Row[Any]) -> ProposalCase:
    """1行を API の型に移す。

    Args:
        row: SEARCH_SQL の1行。

    Returns:
        事例1件。
    """
    return ProposalCase(
        company_id=row.company_id,
        release_id=row.release_id,
        title=row.title,
        subtitle=row.subtitle,
        body_head=row.body_head,
        company_name=row.company_name,
        business_category=row.business_category_name,
        release_type=row.release_type_name,
        prefecture=row.prefecture_name,
        city=row.city_name,
        published_on=row.published_on,
        reach=row.reach,
        # 加点後のスコア。並び替えにしか使わないので加点前に戻さない
        similarity=row.score,
        # 転載ログから引くのは呼び出し側。ここでは空で作る
        media=[],
    )


async def search(
    vector: np.ndarray,
    *,
    business_category_id: int | None = None,
    prefecture_id: int | None = None,
    top_k: int = 8,
) -> list[ProposalCase]:
    """近い事例を返す。意味の近さを主軸に, 同業種・同地域・実際の届き方を加点する。

    Args:
        vector: L2正規化済みのクエリベクトル。
        business_category_id: 顧客の業種。None なら加点しない。
        prefecture_id: 顧客の都道府県。None なら加点しない。
        top_k: 返す件数。

    Returns:
        スコアの降順に並んだ事例。
    """
    params = {
        "vector": vector,
        "business_category_id": business_category_id,
        "prefecture_id": prefecture_id,
        "top_k": top_k,
    }
    async with session() as db:
        rows = (await db.execute(SEARCH_SQL, params)).all()
    return [_case(row) for row in rows]
