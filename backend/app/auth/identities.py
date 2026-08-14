from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.db.models import OAuthIdentity, User


async def upsert_user(db: AsyncSession, *, provider: str, subject: str, email: str | None, name: str) -> User:
    """外部 IdP の識別子からユーザーを引き, 無ければ作る。

    Args:
        db: データベースセッション。
        provider: google など。
        subject: プロバイダ内での一意なID。
        email: プロバイダから得たメールアドレス。
        name: プロバイダから得た表示名。

    Returns:
        紐づくユーザー。
    """
    found = (
        await db.execute(
            select(OAuthIdentity).where(col(OAuthIdentity.provider) == provider, col(OAuthIdentity.subject) == subject)
        )
    ).scalar_one_or_none()

    if found is not None:
        user = await db.get(User, found.user_id)
        if user is not None:
            return user

    user = User(email=email, name=name)
    db.add(user)
    await db.flush()
    db.add(OAuthIdentity(user_id=user.id, provider=provider, subject=subject, email=email))
    await db.commit()
    return user
