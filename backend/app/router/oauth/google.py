import secrets
from datetime import UTC, datetime, timedelta
from typing import Final
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from google.oauth2.credentials import Credentials
from loguru import logger

from app.auth.demo import register
from app.auth.google import REVOKE_ENDPOINT, SCOPES, TOKEN_ENDPOINT, forget_credentials, save_credentials
from app.auth.identities import upsert_user
from app.auth.user_sessions import SESSION_COOKIE, SESSION_MAX_AGE, create_session, revoke_session
from app.calendar import seed_events
from app.dependencies import CurrentUser, DbSessionDep
from app.schema.calendar import DemoLogin
from app.settings import settings

# 経路はフロントとの契約なので /api/calendar のまま置く
router = APIRouter(prefix="/api/calendar", tags=["calendar"])

AUTH_ENDPOINT: Final = "https://accounts.google.com/o/oauth2/v2/auth"

PROVIDER: Final = "google"

# 認可の往復だけ生きていればよい
STATE_COOKIE: Final = "calendar_oauth_state"
STATE_MAX_AGE: Final = 600

HTTP_TIMEOUT_SECONDS: Final = 10


@router.get("/login")
def start_oauth() -> RedirectResponse:
    """Google の同意画面へ送る。state はサーバに持たず Cookie で持ち回る。

    Returns:
        認可 URL へのリダイレクト。

    Raises:
        HTTPException: クライアント ID が設定されていないとき 503。
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
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        max_age=STATE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        # Google からの戻りはトップレベル遷移なので lax で届く
        samesite="lax",
    )
    return response


@router.get("/oauth/callback")
async def oauth_callback(request: Request, code: str, state: str, db: DbSessionDep) -> RedirectResponse:
    """認可コードを交換し, ユーザーを作ってログインさせ, カレンダーのトークンを保存する。

    Args:
        request: state の Cookie とクライアント情報を読むために使う。
        code: Google が返した認可コード。
        state: Google が返した突き合わせ用の値。
        db: データベースセッション。

    Returns:
        フロントへのリダイレクト。セッション Cookie を載せる。

    Raises:
        HTTPException: state が一致しないとき 400。交換や ID token の検証に失敗したとき 502。
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
        raw_id_token = payload["id_token"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid token response from Google.",
        ) from exc

    try:
        claim = google_id_token.verify_oauth2_token(
            raw_id_token,
            google_requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID,
        )
        subject = claim["sub"]
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID token received from Google.",
        ) from exc

    user = await upsert_user(
        db,
        provider=PROVIDER,
        subject=subject,
        email=claim.get("email"),
        name=claim.get("name") or "",
    )

    await save_credentials(
        db,
        user.id,
        Credentials(
            token=access_token,
            refresh_token=payload.get("refresh_token"),
            token_uri=TOKEN_ENDPOINT,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
            scopes=SCOPES,
            # google-auth は naive UTC で比較する
            expiry=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=int(payload.get("expires_in", 0))),
        ),
    )

    token = await create_session(
        db,
        user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    response = RedirectResponse(settings.FRONTEND_URL)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
    response.delete_cookie(STATE_COOKIE, httponly=True, secure=settings.COOKIE_SECURE, samesite="lax")
    return response


@router.post("/demo-login", status_code=status.HTTP_204_NO_CONTENT)
async def demo_login(body: DemoLogin, request: Request, db: DbSessionDep) -> Response:
    """Google を通さず名前だけでログインする。初めての名前なら予定を積んで返す。

    Args:
        body: 表示名。空なら既定の名前を使う。
        request: user-agent と接続元をセッションに残すために使う。
        db: データベースセッション。

    Returns:
        204。セッション Cookie を張る。

    Raises:
        HTTPException: APP_ENV が demo でないとき。
    """
    if not settings.demo_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="デモログインは開いていません",
        )

    user, created = await register(db, body.name)

    # 作った直後だけ積む。2回目以降は本人が動かした結果をそのまま残す
    if created:
        planted = await seed_events(db, user.id)
        logger.info("デモの予定を積んだ 名前={} 件数={}", user.name, planted)

    token = await create_session(
        db,
        user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
    return response


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(request: Request, user: CurrentUser, db: DbSessionDep) -> Response:
    """連携を切る。保存した資格情報を消し, Google 側にも取り消しを伝える。

    Args:
        request: セッション Cookie を読むために使う。
        user: セッションから復元したユーザー。
        db: データベースセッション。

    Returns:
        204。セッション Cookie を消す。
    """
    refresh_token = await forget_credentials(db, user.id)

    # Google 側に伝わらないと, 相手のアカウント設定にこのアプリが残り続ける。
    # 失敗しても手元は消えているので, ここでは止めない
    if refresh_token:
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                await client.post(REVOKE_ENDPOINT, data={"token": refresh_token})
        except httpx.HTTPError:
            logger.warning("Google への取り消しに失敗した。手元の資格情報は消えている")

    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await revoke_session(db, token)

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, httponly=True, secure=settings.COOKIE_SECURE, samesite="lax")
    return response
