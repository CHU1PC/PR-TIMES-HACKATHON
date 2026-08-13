import secrets
from datetime import UTC, datetime, timedelta
from typing import Final
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials

from app.auth.google import SCOPES, TOKEN_ENDPOINT, save_credentials
from app.settings import settings

# 経路はフロントとの契約なので /api/calendar のまま置く
router = APIRouter(prefix="/api/calendar", tags=["calendar"])

AUTH_ENDPOINT: Final = "https://accounts.google.com/o/oauth2/v2/auth"

# 認可の往復だけ生きていればよい
STATE_COOKIE: Final = "calendar_oauth_state"
STATE_MAX_AGE: Final = 600

HTTP_TIMEOUT_SECONDS: Final = 10


def _set_state_cookie(response: RedirectResponse, state: str) -> None:
    """CSRF 照合用の state を Cookie に載せる。

    Args:
        response: 認可画面へのリダイレクト。
        state: 認可 URL に載せた値と同じもの。
    """
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        max_age=STATE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        # Google からの戻りはトップレベル遷移なので lax で届く
        samesite="lax",
    )


@router.get("/login")
def start_oauth() -> RedirectResponse:
    """Google の同意画面へ送る。state はサーバに持たず Cookie で持ち回る。

    Returns:
        認可 URL へのリダイレクト。

    Raises:
        HTTPException: クライアント ID が設定されていないとき。
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google カレンダー連携が設定されていません",
        )

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        # refresh token を貰うために両方要る
        "access_type": "offline",
        "prompt": "consent",
    }

    response = RedirectResponse(f"{AUTH_ENDPOINT}?{urlencode(params)}")
    _set_state_cookie(response, state)
    return response


@router.get("/oauth/callback")
async def oauth_callback(request: Request, code: str, state: str) -> RedirectResponse:
    """認可コードをトークンに交換して保存する。

    Args:
        request: state の Cookie を読むために使う。
        code: Google が返した認可コード。
        state: Google が返した突き合わせ用の値。

    Returns:
        フロントへのリダイレクト。

    Raises:
        HTTPException: state が一致しないとき, またはトークン交換に失敗したとき。
    """
    cookie_state = request.cookies.get(STATE_COOKIE)
    if cookie_state is None or not secrets.compare_digest(cookie_state, state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or missing state parameter. Possible CSRF attack.",
        )

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        token_response = await client.post(
            TOKEN_ENDPOINT,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            },
        )

    if not token_response.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code for tokens.",
        )

    try:
        payload = token_response.json()
        access_token = payload["access_token"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid token response from Google.",
        ) from exc

    save_credentials(
        Credentials(
            token=access_token,
            refresh_token=payload.get("refresh_token"),
            token_uri=TOKEN_ENDPOINT,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
            scopes=SCOPES,
            # google-auth は naive UTC で比較する
            expiry=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=int(payload.get("expires_in", 0))),
        )
    )

    response = RedirectResponse(settings.FRONTEND_URL)
    response.delete_cookie(STATE_COOKIE, httponly=True, secure=settings.COOKIE_SECURE, samesite="lax")
    return response
