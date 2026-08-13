from pathlib import Path
from typing import Final

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# app/auth/google.py から見て backend/。保存先の作り直しは #8
BACKEND_DIR: Final = Path(__file__).resolve().parents[2]

TOKEN_FILE: Final = BACKEND_DIR / "google_token.json"

TOKEN_ENDPOINT: Final = "https://oauth2.googleapis.com/token"  # ruff:ignore[hardcoded-password-string]

SCOPES: Final = ["https://www.googleapis.com/auth/calendar.readonly"]


def load_credentials() -> Credentials | None:
    """保存済みの資格情報を読む。期限切れなら更新して書き戻す。

    Returns:
        使える資格情報。未連携または更新できなければ None。
    """
    if not TOKEN_FILE.exists():
        return None

    credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_credentials(credentials)

    return credentials if credentials.valid else None


def save_credentials(credentials: Credentials) -> None:
    """資格情報を書き出す。

    Args:
        credentials: 保存する資格情報。
    """
    TOKEN_FILE.write_text(credentials.to_json())
