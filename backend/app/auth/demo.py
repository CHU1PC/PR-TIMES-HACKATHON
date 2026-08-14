from typing import Final

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.identities import find_user
from app.db.models import OAuthIdentity, User

# oauth_identities の provider 列に入れる。google と同じ枠で1人を指す
DEMO_PROVIDER: Final = "demo"

DEFAULT_DEMO_NAME: Final = "デモユーザー"

NAME_MAX_LENGTH: Final = 50


def normalize_name(name: str | None) -> str:
    """入力された表示名を整える。空なら既定の名前にする。

    Args:
        name: 画面から渡された名前。

    Returns:
        前後の空白を除き, 長さを詰めた名前。
    """
    trimmed = (name or "").strip()

    if not trimmed:
        return DEFAULT_DEMO_NAME

    return trimmed[:NAME_MAX_LENGTH]


async def register(db: AsyncSession, name: str | None) -> tuple[User, bool]:
    """名前だけでユーザーを引き, 無ければ作る。同じ名前なら同じ人に戻る。

    Args:
        db: データベースセッション。
        name: 画面から渡された名前。空なら既定の名前を使う。

    Returns:
        ユーザーと, 今作ったかどうか。作ったときだけ呼び出し側が初期データを積む。

    Raises:
        IntegrityError: 衝突後の引き直しでも行が見つからないとき。uq 以外の違反。
    """
    resolved = normalize_name(name)

    existing = await find_user(db, provider=DEMO_PROVIDER, subject=resolved)
    if existing is not None:
        return existing, False

    user = User(email=None, name=resolved)
    db.add(user)
    try:
        await db.flush()
        db.add(OAuthIdentity(user_id=user.id, provider=DEMO_PROVIDER, subject=resolved, email=None))
        await db.commit()
    except IntegrityError:
        # 同名の同時登録に負けた → 勝った人に戻る。初期データを積むのは勝った側だけ
        await db.rollback()
        winner = await find_user(db, provider=DEMO_PROVIDER, subject=resolved)
        if winner is None:
            raise
        return winner, False
    return user, True
