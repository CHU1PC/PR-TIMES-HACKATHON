from fastapi import APIRouter

from app.calendar import events, service
from app.schema.calendar import CalendarEvents, CalendarStatus, EventQuery

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
def calendar_status() -> CalendarStatus:
    """連携済みかどうかを返す。

    Returns:
        連携状態。
    """
    return CalendarStatus(connected=service() is not None)


@router.post("/events")
def calendar_events(query: EventQuery) -> CalendarEvents:
    """指定期間の予定を返す。

    Args:
        query: 取得する期間。

    Returns:
        連携状態と予定。未連携なら events は空。
    """
    found = events(time_min=query.time_min, time_max=query.time_max)

    if found is None:
        return CalendarEvents(connected=False, events=[])

    return CalendarEvents(connected=True, events=found)
