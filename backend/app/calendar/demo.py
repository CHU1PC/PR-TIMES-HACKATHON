from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# 時刻は日本時間で組む。UTC で組むと 15:00 が翌日 0:00 になり日付がずれる
from app.calendar.core import JST
from app.db.models import Event

# (今日からの日数, 開始時刻, 所要時間, 件名, 詳細)。終日は開始時刻を None にする。
# 2件を同じ日に置いて, 1日に複数入る見え方も確かめられるようにしてある
_SEED: Final[list[tuple[int, int | None, int, str, str]]] = [
    (-4, 14, 2, "地元紙の取材", "工場見学の様子を撮ってもらう。"),
    (1, 10, 2, "郵便局での取り扱い開始", "9月から窓口に置いてもらう。3店舗から始める。"),
    (1, 15, 1, "新パッケージの撮影", "リニューアルした3商品を撮る。"),
    (4, None, 0, "東京のまつりに出店", "終日の出店。新商品を配る。"),
    (9, 13, 3, "ハッカソン開催", "学生が30人来る。会場は本社の会議室。"),
    (16, 11, 2, "県のものづくり大賞 表彰式", "昨年の改良品が奨励賞に選ばれた。"),
]


def build_seed_events(user_id: UUID) -> list[Event]:
    """デモ用の予定を今日を基準に組み立てる。

    Args:
        user_id: 予定を持たせるユーザー。

    Returns:
        まだ DB に入れていない予定の一覧。
    """
    today = datetime.now(JST).replace(hour=0, minute=0, second=0, microsecond=0)
    built: list[Event] = []

    for offset, hour, hours, title, description in _SEED:
        day = today + timedelta(days=offset)

        if hour is None:
            starts_at = day
            ends_at = day + timedelta(days=1)
        else:
            starts_at = day + timedelta(hours=hour)
            ends_at = starts_at + timedelta(hours=hours)

        built.append(
            Event(
                user_id=user_id,
                title=title,
                description=description,
                location="",
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=hour is None,
            )
        )

    return built


async def seed_events(db: AsyncSession, user_id: UUID) -> int:
    """デモ用の予定をそのユーザーに積む。

    Args:
        db: データベースセッション。
        user_id: 予定を持たせるユーザー。

    Returns:
        積んだ件数。
    """
    built = build_seed_events(user_id)

    db.add_all(built)
    await db.commit()

    return len(built)
