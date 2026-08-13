from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.auth.user_sessions import SESSION_COOKIE, hash_session_token
from app.db.models import User, UserSession
from app.db.session import get_db_session

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(request: Request, db: DbSessionDep) -> User:
    """Cookie のセッショントークンからユーザーを復元する。

    Args:
        request: セッション Cookie を読むために使う。
        db: データベースセッション。

    Returns:
        連携済みのユーザー。

    Raises:
        HTTPException: トークンが無い, 失効している, または対応するユーザーが居ないとき 401。
    """
    token = request.cookies.get(SESSION_COOKIE)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    found = (
        await db.execute(select(UserSession).where(col(UserSession.token_hash) == hash_session_token(token)))
    ).scalar_one_or_none()

    if found is None or found.revoked_at is not None or found.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = await db.get(User, found.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
