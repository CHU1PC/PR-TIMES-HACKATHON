from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """環境変数から読む。ローカルは `uv run --env-file ../.env`, 本番は compose が渡す。"""

    DATABASE_URL: SecretStr = Field(
        default=SecretStr(""),
        description="データベース接続用の URL。ローカルは SSH トンネル, 本番は RDS を直に指す",
    )
    OPENAI_API_KEY: SecretStr = Field(default=SecretStr(""), description="OpenAI の API キー")

    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:5173"],
        description='CORS で許可するオリジン. JSON 配列で渡す (["a","b"]).',
    )


settings = Settings()
