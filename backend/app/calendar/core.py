from datetime import datetime, timedelta, timezone
from typing import Final
from uuid import UUID

from googleapiclient.discovery import Resource, build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.auth.google import load_credentials
from app.calendar.scoring import refresh_scores, sync_google
from app.db.models import Event
from app.schema import PlanDraft
from app.schema.calendar import CalendarEvent, EventCreate

MAX_EVENTS: Final = 250

NO_TITLE: Final = "(タイトルなし)"

# events.location の桁数に合わせる
LOCATION_CHARS: Final = 255

# Postgres は timestamptz を UTC で返す。終日の日付を出すときは日本時間に戻してから切る
JST: Final = timezone(timedelta(hours=9))


async def service(db: AsyncSession, user_id: UUID) -> Resource | None:
    """そのユーザーの Calendar API クライアントを作る。

    Args:
        db: データベースセッション。
        user_id: 対象のユーザー。

    Returns:
        API クライアント。未連携なら None。
    """
    credentials = await load_credentials(db, user_id)

    if credentials is None:
        return None

    return build("calendar", "v3", credentials=credentials)


def _stored(row: Event) -> CalendarEvent:
    """DB の1件を API の型に移す。

    Args:
        row: events テーブルの1行。

    Returns:
        予定1件。
    """
    # 終日は日付だけにする。Google の終日予定と同じ形に揃える
    if row.all_day:
        starts_at = row.starts_at.astimezone(JST).date().isoformat()
        ends_at = row.ends_at.astimezone(JST).date().isoformat()
    else:
        starts_at = row.starts_at.isoformat()
        ends_at = row.ends_at.isoformat()

    return CalendarEvent(
        id=str(row.id),
        title=row.title,
        description=row.description,
        location=row.location,
        start=starts_at,
        end=ends_at,
        html_link=None,
        status="confirmed",
        score=row.score,
        draft=PlanDraft.model_validate(row.draft) if row.draft else None,
    )


async def create_event(db: AsyncSession, user_id: UUID, payload: EventCreate) -> CalendarEvent:
    """画面から足された予定を保存する。

    Args:
        db: データベースセッション。
        user_id: 予定の持ち主。
        payload: 画面から来た内容。

    Returns:
        保存した予定。
    """
    row = Event(
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        starts_at=datetime.fromisoformat(payload.starts_at),
        ends_at=datetime.fromisoformat(payload.ends_at),
        all_day=payload.all_day,
    )

    db.add(row)
    await db.commit()
    await db.refresh(row)
    await refresh_scores(db, [row])

    return _stored(row)


async def save_draft(db: AsyncSession, user_id: UUID, event_id: str, draft: PlanDraft) -> CalendarEvent | None:
    """壁打ちで埋めた内容を予定に貼り付ける。次に開いたとき同じことを聞かないため。

    Args:
        db: データベースセッション。
        user_id: 予定の持ち主。
        event_id: 自分で足した予定なら UUID, Google 由来なら向こうの予定ID。
        draft: 壁打ちで埋めた内容。

    Returns:
        更新後の予定。持ち主が違うか見つからなければ None。
    """
    query = select(Event).where(col(Event.user_id) == user_id)
    try:
        query = query.where(col(Event.id) == UUID(event_id))
    except ValueError:
        # UUID として読めないものは Google 側の予定ID
        query = query.where(col(Event.external_id) == event_id)

    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        return None

    row.draft = draft.model_dump()
    # 壁打ちで聞いた場所は予定に無いことがある。採点にも効くので写す
    if draft.place and not row.location:
        row.location = draft.place[:LOCATION_CHARS]

    db.add(row)
    await db.commit()
    await refresh_scores(db, [row])

    return _stored(row)


async def stored_rows(
    db: AsyncSession,
    user_id: UUID,
    time_min: str | None = None,
    time_max: str | None = None,
) -> list[Event]:
    """このアプリが持つ予定の行を引く。Google から写したぶんも含む。

    Args:
        db: データベースセッション。
        user_id: 対象のユーザー。
        time_min: 取得開始時刻 (RFC3339)。None なら絞らない。
        time_max: 取得終了時刻 (RFC3339)。None なら絞らない。

    Returns:
        期間に入る予定の行。
    """
    query = select(Event).where(col(Event.user_id) == user_id)

    # 期間の指定は Google と同じ RFC3339 で来る
    if time_min:
        query = query.where(col(Event.ends_at) >= datetime.fromisoformat(time_min))

    if time_max:
        query = query.where(col(Event.starts_at) <= datetime.fromisoformat(time_max))

    return list((await db.execute(query.order_by(col(Event.starts_at)))).scalars().all())


async def events(
    db: AsyncSession,
    user_id: UUID,
    time_min: str | None = None,
    time_max: str | None = None,
) -> list[CalendarEvent]:
    """そのユーザーの予定を引く。

    Args:
        db: データベースセッション。
        user_id: 対象のユーザー。
        time_min: 取得開始時刻 (RFC3339)。None なら指定しない。
        time_max: 取得終了時刻 (RFC3339)。None なら指定しない。

    Returns:
        このアプリに登録された予定と, 連携していれば Google の予定を合わせたもの。
    """
    client = await service(db, user_id)

    if client is not None:
        params: dict[str, str | bool | int] = {
            "calendarId": "primary",
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": MAX_EVENTS,
        }

        if time_min:
            params["timeMin"] = time_min

        if time_max:
            params["timeMax"] = time_max

        found = client.events().list(**params).execute()
        # 採点は DB の行に持たせるので, Google のぶんも写してから読み直す
        await sync_google(db, user_id, [event for item in found.get("items", []) if (event := _event(item))], JST)

    rows = await stored_rows(db, user_id, time_min, time_max)
    await refresh_scores(db, rows)

    return sorted((_stored(row) for row in rows), key=lambda event: event.start)


def _event(item: dict) -> CalendarEvent | None:
    """Google の1件を API の型に移す。

    Args:
        item: events().list() が返す1件。

    Returns:
        予定1件。ID と開始終了が揃わないものは None。
    """
    start = item.get("start", {})
    end = item.get("end", {})

    # 終日の予定は dateTime を持たず date だけになる
    starts_at = start.get("dateTime", start.get("date"))
    ends_at = end.get("dateTime", end.get("date"))
    identifier = item.get("id")

    # 描けない予定は落として非 null を保証する
    if not (identifier and starts_at and ends_at):
        return None

    return CalendarEvent(
        id=identifier,
        title=item.get("summary", NO_TITLE),
        description=item.get("description", ""),
        location=item.get("location", ""),
        start=starts_at,
        end=ends_at,
        html_link=item.get("htmlLink"),
        status=item.get("status"),
        # 採点も壁打ちも取り込んでから。ここでは埋めない
        score=None,
        draft=None,
    )
