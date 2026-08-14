from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from loguru import logger
from openai import OpenAIError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event
from app.llm.embeddings import embed_many
from app.ranking import plan_score
from app.retrieval.place import resolve_prefecture
from app.schema.calendar import CalendarEvent

# 終日の予定は日付だけで来る
DATE_LENGTH: Final = 10

# 詳細は長いことがある。採点に効くのは冒頭なので切る
DESCRIPTION_CHARS: Final = 500

# events の VARCHAR(255) に合わせる。超えたまま入れると INSERT が落ち続ける
TITLE_CHARS: Final = 255
LOCATION_CHARS: Final = 255

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


def sync_values(user_id: UUID, event: CalendarEvent, jst: datetime.tzinfo) -> dict[str, object]:
    """Google の1件を events の列に写す。列の桁に収まるよう切る。

    Args:
        user_id: 予定の持ち主。
        event: Google から取った予定。
        jst: 終日の日付に付ける時間帯。

    Returns:
        INSERT に渡す列の値。
    """
    return {
        "user_id": user_id,
        "source": GOOGLE,
        "external_id": event.id,
        "title": event.title[:TITLE_CHARS],
        "description": event.description,
        "location": event.location[:LOCATION_CHARS],
        "starts_at": parse_moment(event.start, jst),
        "ends_at": parse_moment(event.end, jst),
        "all_day": len(event.start) == DATE_LENGTH,
        # created_at は sa_column 指定のため Core の INSERT に既定値が付かない
        "created_at": datetime.now(UTC),
    }


def sync_updates(values: dict[str, object]) -> dict[str, object]:
    """ON CONFLICT で上書きする列を選ぶ。壁打ちが埋めた場所を空で潰さない。

    Args:
        values: sync_values が組んだ列の値。

    Returns:
        UPDATE に渡す列の値。
    """
    updates = {key: values[key] for key in ("title", "description", "starts_at", "ends_at", "all_day")}
    if values["location"]:
        updates["location"] = values["location"]
    return updates


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

    # 同じユーザーの取得が同時に走っても uq_events_user_external で落ちないよう upsert
    for event in fetched:
        values = sync_values(user_id, event, jst)
        statement = (
            insert(Event)
            .values(values)
            .on_conflict_do_update(index_elements=["user_id", "external_id"], set_=sync_updates(values))
        )
        await db.execute(statement)

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

    scored = 0
    for row, text, vector in zip(stale, texts, vectors, strict=True):
        try:
            prefecture_id = await resolve_prefecture(row.location)
            score = await plan_score(vector, prefecture_id=prefecture_id, db=db)
        except Exception as error:  # ruff: ignore[blind-except] — 1行の失敗で他の行を巻き込まない
            logger.warning("採点に失敗 id={}: {}", row.id, error)
            continue
        row.score = score
        row.scored_text = text
        row.embedding = vector
        db.add(row)
        scored += 1

    if scored:
        await db.commit()
        logger.info("採点 {}件", scored)
