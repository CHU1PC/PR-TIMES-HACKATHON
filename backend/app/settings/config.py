from pydantic import Field, SecretStr, model_validator
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

    # 使わないなら空でよい
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

    APP_ENV: str = Field(
        default="production",
        description='"demo" のときだけ Google なしのデモログインを開く. 既定は塞いだまま',
    )

    @property
    def demo_enabled(self) -> bool:
        """デモログインを開いてよいか。

        Returns:
            APP_ENV が demo のとき True。
        """
        return self.APP_ENV == "demo"

    @model_validator(mode="after")
    def _forbid_wildcard_origin(self) -> "Settings":
        """Cookie を送るので許可先を絞る。

        Returns:
            検証済みの設定。

        Raises:
            ValueError: ALLOWED_ORIGINS に * が入っているとき。
        """
        if "*" in self.ALLOWED_ORIGINS:
            msg = "ALLOWED_ORIGINS に * は使えない。セッション Cookie を送るので許可先を明示する"
            raise ValueError(msg)
        return self


settings = Settings()
