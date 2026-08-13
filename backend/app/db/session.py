import functools
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.settings import API_STATEMENT_TIMEOUT, settings

SYNC_SCHEME = "postgresql://"
ASYNC_SCHEME = "postgresql+psycopg://"

CONNECT_OPTIONS = f"-c statement_timeout={API_STATEMENT_TIMEOUT}"

POOL_SIZE = 5
MAX_OVERFLOW = 5


@functools.cache
def engine() -> AsyncEngine:
    """エンジンを初回参照時に1つだけ作る。import では接続しない。

    Returns:
        使い回す非同期エンジン。
    """
    url = settings.DATABASE_URL.get_secret_value()
    if url.startswith(SYNC_SCHEME):
        url = ASYNC_SCHEME + url[len(SYNC_SCHEME) :]
    return create_async_engine(
        url,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_pre_ping=True,
        connect_args={"options": CONNECT_OPTIONS},
    )


@asynccontextmanager
async def session() -> AsyncGenerator[AsyncSession]:
    """セッションを1つ開き, 抜けたら閉じる。

    Yields:
        非同期セッション。
    """
    async with AsyncSession(engine(), expire_on_commit=False) as opened:
        yield opened


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI の依存として1リクエスト1セッションを配る。

    例外時は明示的に rollback する。中途半端な変更を接続プールに戻さない。

    Yields:
        非同期セッション。
    """
    opened = AsyncSession(engine(), expire_on_commit=False)
    try:
        yield opened
    except BaseException:
        await opened.rollback()
        raise
    finally:
        await opened.close()
