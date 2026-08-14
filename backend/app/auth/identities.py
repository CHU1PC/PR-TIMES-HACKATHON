from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.db.models import OAuthIdentity, User


async def find_user(db: AsyncSession, *, provider: str, subject: str) -> User | None:
    """外部 IdP の識別子からユーザーを引く。

    Args:
        db: データベースセッション。
        provider: google など。
        subject: プロバイダ内での一意なID。

    Returns:
        紐づくユーザー。無ければ None。
    """
    found = (
        await db.execute(
            select(OAuthIdentity).where(col(OAuthIdentity.provider) == provider, col(OAuthIdentity.subject) == subject)
        )
    ).scalar_one_or_none()

    if found is None:
        return None
    return await db.get(User, found.user_id)


async def upsert_user(db: AsyncSession, *, provider: str, subject: str, email: str | None, name: str) -> User:
    """外部 IdP の識別子からユーザーを引き, 無ければ作る。同時の初回ログインは先に入った行に合流する。

    Args:
        db: データベースセッション。
        provider: google など。
        subject: プロバイダ内での一意なID。
        email: プロバイダから得たメールアドレス。
        name: プロバイダから得た表示名。

    Returns:
        紐づくユーザー。

    Raises:
        IntegrityError: 衝突後の引き直しでも行が見つからないとき。uq 以外の違反。
    """
    existing = await find_user(db, provider=provider, subject=subject)
    if existing is not None:
        return existing

    user = User(email=email, name=name)
    db.add(user)
    try:
        await db.flush()
        db.add(OAuthIdentity(user_id=user.id, provider=provider, subject=subject, email=email))
        await db.commit()
    except IntegrityError:
        # uq_provider_subject に負けた → rollback して勝った行を返す
        await db.rollback()
        winner = await find_user(db, provider=provider, subject=subject)
        if winner is None:
            raise
        return winner
    return user
