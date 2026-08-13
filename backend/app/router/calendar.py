from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.calendar import (
    get_authorization_url,
    get_calendar_service,
    get_events,
    save_authorization_code,
)

router = APIRouter(
    prefix="/api/calendar",
    tags=["calendar"],
)

BAD_REQUEST = 400

# 連携後にフロントへ戻す先
AFTER_CALLBACK_URL = "http://localhost:5173/"


class EventQuery(BaseModel):
    """予定を引く期間。キーは Google Calendar API の名前に合わせる。"""

    time_min: str | None = Field(default=None, alias="timeMin", description="取得開始時刻 (RFC3339)")
    time_max: str | None = Field(default=None, alias="timeMax", description="取得終了時刻 (RFC3339)")


# state から PKCE の code_verifier を引くための一時置き場
oauth_sessions: dict[str, str] = {}


@router.get("/login")
def calendar_login() -> RedirectResponse:
    """Google の同意画面へ送る。

    Returns:
        認可 URL へのリダイレクト。
    """
    authorization_url, state, code_verifier = get_authorization_url()

    oauth_sessions[state] = code_verifier

    return RedirectResponse(authorization_url)


@router.get("/oauth/callback")
def calendar_callback(code: str, state: str | None = None) -> RedirectResponse:
    """認可コードを受け取ってトークンに交換する。

    Args:
        code: Google が返した認可コード。
        state: 認可 URL を作ったときに渡した突き合わせ用の値。

    Returns:
        フロントへのリダイレクト。

    Raises:
        HTTPException: state が無いか, 対応する session が見つからないとき。
    """
    if not state:
        raise HTTPException(
            status_code=BAD_REQUEST,
            detail="Missing OAuth state",
        )

    code_verifier = oauth_sessions.pop(state, None)

    if not code_verifier:
        raise HTTPException(
            status_code=BAD_REQUEST,
            detail="Invalid or expired OAuth session",
        )

    save_authorization_code(code, code_verifier)

    return RedirectResponse(AFTER_CALLBACK_URL)


@router.get("/status")
def calendar_status() -> dict[str, bool]:
    """連携済みかどうかを返す。

    Returns:
        connected に連携状態。
    """
    service = get_calendar_service()

    return {"connected": service is not None}


@router.post("/events")
def calendar_events(query: EventQuery) -> dict[str, bool | list[dict[str, str | None]]]:
    """指定期間の予定を返す。

    Args:
        query: 取得する期間。

    Returns:
        connected と events。未連携なら events は空。
    """
    events = get_events(
        time_min=query.time_min,
        time_max=query.time_max,
    )

    if events is None:
        return {"connected": False, "events": []}

    return {"connected": True, "events": events}
