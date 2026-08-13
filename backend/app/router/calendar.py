from fastapi import APIRouter, Request

from app.calendar import events, service
from app.dependencies import CurrentUser, DbSessionDep, get_current_user
from app.schema.calendar import CalendarEvents, CalendarStatus, EventQuery
from app.settings import settings

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
async def calendar_status(request: Request, db: DbSessionDep) -> CalendarStatus:
    """ログイン済みか, この環境で連携が使えるか, この人が連携済みかを返す。

    未ログインでも 401 にせず signed_in=false を返す。ログインボタンを出す判断に使うため。

    Args:
        request: セッション Cookie を読むために使う。
        db: データベースセッション。

    Returns:
        ログインと連携の状況。
    """
    configured = bool(settings.GOOGLE_CLIENT_ID)
    demo = settings.demo_enabled

    try:
        user = await get_current_user(request, db)
    except Exception:  # ruff: ignore[blind-except] — 未ログインも失効も同じに扱う
        return CalendarStatus(signed_in=False, configured=configured, connected=False, demo=demo)

    return CalendarStatus(
        signed_in=True,
        configured=configured,
        connected=await service(db, user.id) is not None,
        demo=demo,
    )


@router.post("/events")
async def calendar_events(query: EventQuery, user: CurrentUser, db: DbSessionDep) -> CalendarEvents:
    """ログイン中の本人の予定だけを返す。

    Args:
        query: 取得する期間。
        user: セッションから復元したユーザー。
        db: データベースセッション。

    Returns:
        Google の連携状態と予定。連携していなくても自分で足した予定は返る。
    """
    found = await events(db, user.id, time_min=query.time_min, time_max=query.time_max)

    return CalendarEvents(connected=await service(db, user.id) is not None, events=found)

    return CalendarEvents(connected=True, events=found)
