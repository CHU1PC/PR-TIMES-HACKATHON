import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import Resource, build

BASE_DIR = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]

MAX_EVENTS = 250

REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/calendar/oauth/callback",
)


def create_flow() -> Flow:
    """OAuth の遷移を組み立てる。

    Returns:
        認可 URL の生成とトークン交換に使う Flow。
    """
    return Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def get_credentials() -> Credentials | None:
    """保存済みのトークンを読む。期限切れなら更新して書き戻す。

    Returns:
        使える資格情報。未連携または更新できなければ None。
    """
    if not TOKEN_FILE.exists():
        return None

    creds = Credentials.from_authorized_user_file(
        str(TOKEN_FILE),
        SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    if creds.valid:
        return creds

    return None


def get_authorization_url() -> tuple[str, str, str]:
    """同意画面の URL を作る。

    Returns:
        認可 URL, 突き合わせ用の state, PKCE の code_verifier。
    """
    flow = create_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return authorization_url, state, flow.code_verifier


def save_authorization_code(code: str, code_verifier: str) -> Credentials:
    """認可コードをトークンに交換して保存する。

    Args:
        code: コールバックで受け取った認可コード。
        code_verifier: 認可 URL を作ったときの PKCE 値。

    Returns:
        交換して得た資格情報。
    """
    flow = create_flow()

    flow.code_verifier = code_verifier

    flow.fetch_token(code=code)

    TOKEN_FILE.write_text(flow.credentials.to_json())

    return flow.credentials


def get_calendar_service() -> Resource | None:
    """Calendar API のクライアントを作る。

    Returns:
        API クライアント。未連携なら None。
    """
    credentials = get_credentials()

    if credentials is None:
        return None

    return build(
        "calendar",
        "v3",
        credentials=credentials,
    )


def get_events(
    time_min: str | None = None,
    time_max: str | None = None,
) -> list[dict[str, str | None]] | None:
    """主カレンダーの予定を引く。

    Args:
        time_min: 取得開始時刻 (RFC3339)。None なら指定しない。
        time_max: 取得終了時刻 (RFC3339)。None なら指定しない。

    Returns:
        予定の一覧。未連携なら None。
    """
    service = get_calendar_service()

    if service is None:
        return None

    params: dict[str, str | bool | int] = {
        "calendarId": "primary",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": MAX_EVENTS,
    }

    if time_min:
        params["timeMin"] = time_min

    if time_max:
        params["timeMax"] = time_max

    result = service.events().list(**params).execute()

    events: list[dict[str, str | None]] = []

    for event in result.get("items", []):
        start = event.get("start", {})
        end = event.get("end", {})

        events.append(
            {
                "id": event.get("id"),
                "title": event.get("summary", "(タイトルなし)"),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "start": start.get("dateTime", start.get("date")),
                "end": end.get("dateTime", end.get("date")),
                "htmlLink": event.get("htmlLink"),
                "status": event.get("status"),
            }
        )

    return events
