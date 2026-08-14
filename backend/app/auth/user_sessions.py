import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.db.models import SESSION_EXPIRY_DAYS, UserSession

SESSION_COOKIE: Final = "session_token"
SESSION_MAX_AGE: Final = SESSION_EXPIRY_DAYS * 24 * 60 * 60

_TOKEN_BYTES: Final = 32


def hash_session_token(token: str) -> str:
    """セッショントークンをハッシュ化する。

    Args:
        token: Cookie に載せる生のトークン。

    Returns:
        SHA-256 の hex。DB にはこちらだけを置き, 漏れても Cookie を復元できないようにする。
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    """セッションを1つ発行する。

    Args:
        db: データベースセッション。
        user_id: 対象のユーザー。
        user_agent: クライアントの User-Agent。
        ip_address: クライアントの IP。

    Returns:
        Cookie に載せる生のトークン。保存はしない。
    """
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    db.add(
        UserSession(
            user_id=user_id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=SESSION_EXPIRY_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    await db.commit()
    return token


async def revoke_session(db: AsyncSession, token: str) -> None:
    """セッションを失効させる。行は監査のため残す。

    Args:
        db: データベースセッション。
        token: Cookie に入っていた生のトークン。
    """
    found = (
        await db.execute(select(UserSession).where(col(UserSession.token_hash) == hash_session_token(token)))
    ).scalar_one_or_none()

    if found is not None and found.revoked_at is None:
        found.revoked_at = datetime.now(UTC)
        await db.commit()
