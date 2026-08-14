from datetime import datetime
from typing import Final
from uuid import UUID

from loguru import logger
from openai import OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.db.models import Event
from app.llm.embeddings import embed_many
from app.ranking import plan_score
from app.retrieval.place import resolve_prefecture
from app.schema.calendar import CalendarEvent

# 終日の予定は日付だけで来る
DATE_LENGTH: Final = 10

# 詳細は長いことがある。採点に効くのは冒頭なので切る
DESCRIPTION_CHARS: Final = 500

GOOGLE: Final = "google"


def scored_text(title: str, location: str, description: str) -> str:
    """採点に使う本文を組み立てる。

    Args:
        title: 予定の件名。
        location: 場所。
        description: 予定の詳細。

    Returns:
        埋め込みに渡す文字列。
    """
    return "\n".join(filter(None, (title, location, description[:DESCRIPTION_CHARS])))


def parse_moment(value: str, jst: datetime.tzinfo) -> datetime:
    """Google の開始終了を datetime に直す。

    Args:
        value: RFC3339 か YYYY-MM-DD。
        jst: 終日の日付に付ける時間帯。

    Returns:
        時間帯つきの日時。
    """
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=jst) if parsed.tzinfo is None else parsed


async def sync_google(db: AsyncSession, user_id: UUID, fetched: list[CalendarEvent], jst: datetime.tzinfo) -> None:
    """Google の予定を events に写す。採点のために持つだけで, 消えた予定は追わない。

    Args:
        db: データベースセッション。
        user_id: 予定の持ち主。
        fetched: Google から取った予定。
        jst: 終日の日付に付ける時間帯。
    """
    if not fetched:
        return

    identifiers = [event.id for event in fetched]
    query = select(Event).where(col(Event.user_id) == user_id, col(Event.external_id).in_(identifiers))
    known = {row.external_id: row for row in (await db.execute(query)).scalars().all()}

    for event in fetched:
        row = known.get(event.id) or Event(
            user_id=user_id,
            source=GOOGLE,
            external_id=event.id,
            starts_at=parse_moment(event.start, jst),
            ends_at=parse_moment(event.end, jst),
        )
        row.title = event.title
        row.description = event.description
        row.location = event.location
        row.starts_at = parse_moment(event.start, jst)
        row.ends_at = parse_moment(event.end, jst)
        row.all_day = len(event.start) == DATE_LENGTH
        db.add(row)

    await db.commit()


async def refresh_scores(db: AsyncSession, rows: list[Event]) -> None:
    """本文が変わった予定だけ埋め込み直して採点する。

    Args:
        db: データベースセッション。
        rows: 対象の予定。
    """
    stale = [row for row in rows if row.scored_text != scored_text(row.title, row.location, row.description)]
    if not stale:
        return

    texts = [scored_text(row.title, row.location, row.description) for row in stale]
    try:
        vectors = await embed_many(texts)
    except OpenAIError as error:
        # 採点できなくてもカレンダーは出す
        logger.warning("採点の埋め込みに失敗 {}件: {}", len(stale), error)
        return

    for row, text, vector in zip(stale, texts, vectors, strict=True):
        prefecture_id = await resolve_prefecture(row.location)
        row.score = await plan_score(vector, prefecture_id=prefecture_id)
        row.scored_text = text
        row.embedding = vector
        db.add(row)

    await db.commit()
    logger.info("採点 {}件", len(stale))
