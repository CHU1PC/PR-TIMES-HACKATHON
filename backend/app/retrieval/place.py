import asyncio
from collections import Counter

from sqlalchemy import text

from app.db import session

# 「東京」「大阪」のように接尾辞を落として書かれても拾う。「道」は落とすと北海道が「北海」になるので残す
DROPPABLE_SUFFIXES = "都府県"

# 接尾辞を落としても2文字は残す。「京都府」を1文字にすると「文京区」に当たる
MIN_SHORT_LENGTH = 2

# 反復順で結果が変わらないよう ID 順に固定する
PLACES_SQL = text("SELECT kind, name, prefecture_id FROM places ORDER BY prefecture_id, name")


# places は数千行と小さいので初回に読み切って使い回す（async 関数には functools.cache が使えない）
_prefectures: dict[str, int] = {}
_cities: list[tuple[str, int]] = []
_lock = asyncio.Lock()


async def _tables() -> tuple[dict[str, int], list[tuple[str, int]]]:
    """地名の索引を1度だけ読み込む。

    Returns:
        都道府県名 → ID と, (市区町村名, 都道府県ID) の一覧。
    """
    # extend は冪等でないので, 同時に2本走ると市区町村が重複して多数決が壊れる
    async with _lock:
        if not _prefectures:
            async with session() as db:
                rows = (await db.execute(PLACES_SQL)).all()
            _prefectures.update({name: pref for kind, name, pref in rows if kind == "prefecture"})
            _cities.extend((name, pref) for kind, name, pref in rows if kind == "city")
    return _prefectures, _cities


async def resolve_prefecture(place: str | None) -> int | None:
    """自由入力の地名から都道府県IDを引く。

    Args:
        place: 「熊本市中央区」「山梨県」「オンライン」など。

    Returns:
        都道府県ID。判別できなければ None。
    """
    if not place:
        return None
    prefectures, cities = await _tables()

    # 完全名を先に見る。「東京都文京区」は短縮形だと「京都」にも当たる
    for name, pref in prefectures.items():
        if name in place:
            return pref
    for name, pref in prefectures.items():
        short = name[:-1] if len(name) > MIN_SHORT_LENGTH and name[-1] in DROPPABLE_SUFFIXES else name
        if short in place:
            return pref

    # 市区町村名は「中央区」のように県をまたいで重複する。一致した数が多い県を採る
    hits = Counter(pref for name, pref in cities if name in place)
    if not hits:
        return None
    top = hits.most_common(2)
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None
    return top[0][0]
