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

    FRONTEND_URL: str = Field(
        default="http://localhost:5173",
        description="連携を終えたあとに戻す先",
    )

    # カレンダーを使わないなら空でよい。空のまま /api/calendar/login を叩くと 503 で返す
    GOOGLE_CLIENT_ID: str = Field(default="", description="OAuth 2.0 のクライアント ID")
    GOOGLE_CLIENT_SECRET: SecretStr = Field(default=SecretStr(""), description="OAuth 2.0 のクライアントシークレット")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/calendar/oauth/callback",
        description="Google Cloud Console の Authorized redirect URIs と完全一致させる",
    )

    COOKIE_SECURE: bool = Field(
        default=True,
        description="Cookie に Secure を付ける. HTTP のローカル開発でだけ false にする",
    )


settings = Settings()
