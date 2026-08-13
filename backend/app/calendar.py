from pathlib import Path
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]

REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/calendar/oauth/callback",
)


def create_flow():
    return Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def get_credentials():
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


def get_authorization_url():
    flow = create_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return authorization_url, state, flow.code_verifier


def save_authorization_code(code: str, code_verifier: str):
    flow = create_flow()

    flow.code_verifier = code_verifier

    flow.fetch_token(code=code)

    TOKEN_FILE.write_text(
        flow.credentials.to_json()
    )

    return flow.credentials


def get_calendar_service():
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
):
    service = get_calendar_service()

    if service is None:
        return None

    params = {
        "calendarId": "primary",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 250,
    }

    if time_min:
        params["timeMin"] = time_min

    if time_max:
        params["timeMax"] = time_max

    result = (
        service.events()
        .list(**params)
        .execute()
    )

    events = []

    for event in result.get("items", []):
        start = event.get("start", {})
        end = event.get("end", {})

        events.append(
            {
                "id": event.get("id"),
                "title": event.get("summary", "(タイトルなし)"),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "start": start.get(
                    "dateTime",
                    start.get("date"),
                ),
                "end": end.get(
                    "dateTime",
                    end.get("date"),
                ),
                "htmlLink": event.get("htmlLink"),
                "status": event.get("status"),
            }
        )

    return events