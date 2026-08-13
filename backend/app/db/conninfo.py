from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg

from app.settings import API_STATEMENT_TIMEOUT, READ_ONLY_SQL, settings

CONNECT_TIMEOUT_SECONDS = 10


@asynccontextmanager
async def rds_connection() -> AsyncGenerator[psycopg.AsyncConnection]:
    """RDS への接続を1つ開く。接続先は DATABASE_URL が決める。

    Yields:
        読み取り専用・タイムアウト設定済みの非同期接続。
    """
    conn = await psycopg.AsyncConnection.connect(
        settings.DATABASE_URL.get_secret_value(),
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        autocommit=True,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(f"SET statement_timeout = '{API_STATEMENT_TIMEOUT}'")
            await cur.execute(READ_ONLY_SQL)
        yield conn
    finally:
        await conn.close()
