import json
from typing import Final
from uuid import UUID

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.db.models import GoogleCredential

TOKEN_ENDPOINT: Final = "https://oauth2.googleapis.com/token"  # ruff:ignore[hardcoded-password-string]

# サインインとカレンダー読み取りを1回の同意でまとめて取る
SCOPES: Final = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar.readonly",
]


async def load_credentials(db: AsyncSession, user_id: UUID) -> Credentials | None:
    """そのユーザーの資格情報を読む。期限切れなら更新して書き戻す。

    Args:
        db: データベースセッション。
        user_id: 対象のユーザー。

    Returns:
        使える資格情報。未連携または更新できなければ None。
    """
    row = (
        await db.execute(select(GoogleCredential).where(col(GoogleCredential.user_id) == user_id))
    ).scalar_one_or_none()

    if row is None:
        return None

    credentials = Credentials.from_authorized_user_info(json.loads(row.token_json), SCOPES)

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except RefreshError:
            return None
        row.token_json = credentials.to_json()
        await db.commit()

    return credentials if credentials.valid else None


async def save_credentials(db: AsyncSession, user_id: UUID, credentials: Credentials) -> None:
    """資格情報を保存する。連携し直したら上書きする。

    Args:
        db: データベースセッション。
        user_id: 対象のユーザー。
        credentials: 保存する資格情報。
    """
    row = (
        await db.execute(select(GoogleCredential).where(col(GoogleCredential.user_id) == user_id))
    ).scalar_one_or_none()

    if row is None:
        db.add(GoogleCredential(user_id=user_id, token_json=credentials.to_json()))
    else:
        row.token_json = credentials.to_json()

    await db.commit()
