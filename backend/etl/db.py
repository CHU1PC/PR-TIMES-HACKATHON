import psycopg

from app.settings import READ_ONLY_SQL, settings

CONNECT_TIMEOUT_SECONDS = 15


async def connect(statement_timeout: str) -> psycopg.AsyncConnection:
    """ETL 用に RDS へ接続する。接続先は DATABASE_URL が決める。

    Args:
        statement_timeout: Postgres の statement_timeout。チャンクが収まる値を呼び出し側が決める。

    Returns:
        読み取り専用・タイムアウト設定済みの非同期接続。
    """
    conn = await psycopg.AsyncConnection.connect(
        settings.DATABASE_URL.get_secret_value(),
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        autocommit=True,
    )
    async with conn.cursor() as cur:
        await cur.execute(f"SET statement_timeout = '{statement_timeout}'")
        await cur.execute(READ_ONLY_SQL)
    return conn
