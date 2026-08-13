from fastapi import APIRouter, Request

from app.calendar import events, service
from app.dependencies import CurrentUser, DbSessionDep, get_current_user
from app.schema.calendar import CalendarEvents, CalendarStatus, EventQuery
from app.settings import settings

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
async def calendar_status(request: Request, db: DbSessionDep) -> CalendarStatus:
    """この環境で連携が使えるか, そしてこの人が連携済みかを返す。

    未ログインでも 401 にせず connected=false を返す。連携ボタンを出す判断に使うため。

    Args:
        request: セッション Cookie を読むために使う。
        db: データベースセッション。

    Returns:
        設定状況と連携状況。
    """
    configured = bool(settings.GOOGLE_CLIENT_ID)

    try:
        user = await get_current_user(request, db)
    except Exception:  # ruff: ignore[blind-except] — 未ログインも失効も「未連携」として同じに扱う
        return CalendarStatus(configured=configured, connected=False)

    return CalendarStatus(configured=configured, connected=await service(db, user.id) is not None)


@router.post("/events")
async def calendar_events(query: EventQuery, user: CurrentUser, db: DbSessionDep) -> CalendarEvents:
    """ログイン中の本人の予定だけを返す。

    Args:
        query: 取得する期間。
        user: セッションから復元したユーザー。
        db: データベースセッション。

    Returns:
        連携状態と予定。未連携なら events は空。
    """
    found = await events(db, user.id, time_min=query.time_min, time_max=query.time_max)

    if found is None:
        return CalendarEvents(connected=False, events=[])

    return CalendarEvents(connected=True, events=found)
