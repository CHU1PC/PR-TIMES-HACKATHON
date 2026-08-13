import functools
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.settings import API_STATEMENT_TIMEOUT, settings

# 素の postgresql:// は同期ドライバに落ちる。psycopg3 の async を明示する
SYNC_SCHEME = "postgresql://"
ASYNC_SCHEME = "postgresql+psycopg://"

# libpq の options として接続時に渡す。
# 読み取り専用にはしない。この DB は将来ユーザーやセッションの書き込みも受ける
CONNECT_OPTIONS = f"-c statement_timeout={API_STATEMENT_TIMEOUT}"

# 1リクエスト1クエリなので細くてよい。RDS の接続上限を1タスクで食い潰さない
POOL_SIZE = 5
MAX_OVERFLOW = 5


def async_url() -> str:
    """DATABASE_URL を async ドライバ付きの形に直す。

    Returns:
        create_async_engine に渡す URL。
    """
    url = settings.DATABASE_URL.get_secret_value()
    if url.startswith(SYNC_SCHEME):
        return ASYNC_SCHEME + url[len(SYNC_SCHEME) :]
    return url


@functools.cache
def engine() -> AsyncEngine:
    """エンジンを初回参照時に1つだけ作る。import では接続しない。

    Returns:
        使い回す非同期エンジン。
    """
    return create_async_engine(
        async_url(),
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_pre_ping=True,
        connect_args={"options": CONNECT_OPTIONS},
    )


@functools.cache
def _sessions() -> async_sessionmaker[AsyncSession]:
    """セッション生成器を1つだけ持つ。

    Returns:
        使い回す async_sessionmaker。
    """
    return async_sessionmaker(engine(), expire_on_commit=False)


@asynccontextmanager
async def session() -> AsyncGenerator[AsyncSession]:
    """セッションを1つ開き, 抜けたら閉じる。

    Yields:
        非同期セッション。
    """
    async with _sessions()() as opened:
        yield opened
