from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel

from alembic import context
from app.db import models  # ruff: ignore[unused-import]
from app.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# postgresql:// のままだと psycopg2 を探しに行く。% は ConfigParser の補間に食われる
_url = make_url(settings.DATABASE_URL.get_secret_value()).set(drivername="postgresql+psycopg")
config.set_main_option("sqlalchemy.url", _url.render_as_string(hide_password=False).replace("%", "%%"))

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """接続せずに SQL を出力する。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """実際に接続して流す。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
