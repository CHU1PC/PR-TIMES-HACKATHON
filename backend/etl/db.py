import psycopg

from app.settings import READ_ONLY_SQL, settings

CONNECT_TIMEOUT_SECONDS = 15


async def connect(statement_timeout: str) -> psycopg.AsyncConnection:
    """抽出元である主催者の RDS へ繋ぐ。投入先の DATABASE_URL とは別の DB。

    Args:
        statement_timeout: Postgres の statement_timeout。チャンクが収まる値を呼び出し側が決める。

    Returns:
        読み取り専用・タイムアウト設定済みの非同期接続。
    """
    conn = await psycopg.AsyncConnection.connect(
        settings.SOURCE_DATABASE_URL.get_secret_value(),
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        autocommit=True,
    )
    async with conn.cursor() as cur:
        await cur.execute(f"SET statement_timeout = '{statement_timeout}'")
        await cur.execute(READ_ONLY_SQL)
    return conn
