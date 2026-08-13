from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """環境変数から読む。ローカルは `uv run --env-file ../.env`, 本番は ECS が Parameter Store から渡す。"""

    DATABASE_URL: SecretStr = Field(
        default=SecretStr(""),
        description="このアプリの RDS。API と alembic と etl.load_corpus が書き込む",
    )
    SOURCE_DATABASE_URL: SecretStr = Field(
        default=SecretStr(""),
        description="主催者の RDS。etl の抽出だけが読む。DDL は打たない",
    )
    OPENAI_API_KEY: SecretStr = Field(default=SecretStr(""), description="OpenAI の API キー")

    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:5173"],
        description='CORS で許可するオリジン. JSON 配列で渡す (["a","b"]).',
    )


settings = Settings()
