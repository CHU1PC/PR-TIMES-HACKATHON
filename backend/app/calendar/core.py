from typing import Final

from googleapiclient.discovery import Resource, build

from app.auth.google import load_credentials
from app.schema.calendar import CalendarEvent

MAX_EVENTS: Final = 250

NO_TITLE: Final = "(タイトルなし)"


def service() -> Resource | None:
    """Calendar API のクライアントを作る。

    Returns:
        API クライアント。未連携なら None。
    """
    credentials = load_credentials()

    if credentials is None:
        return None

    return build("calendar", "v3", credentials=credentials)


def events(time_min: str | None = None, time_max: str | None = None) -> list[CalendarEvent] | None:
    """主カレンダーの予定を引く。

    Args:
        time_min: 取得開始時刻 (RFC3339)。None なら指定しない。
        time_max: 取得終了時刻 (RFC3339)。None なら指定しない。

    Returns:
        予定の一覧。未連携なら None。
    """
    client = service()

    if client is None:
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

    found = client.events().list(**params).execute()

    return [event for item in found.get("items", []) if (event := _event(item))]


def _event(item: dict) -> CalendarEvent | None:
    """Google の1件を API の型に移す。

    Args:
        item: events().list() が返す1件。

    Returns:
        予定1件。ID と開始終了が揃わないものは None。
    """
    start = item.get("start", {})
    end = item.get("end", {})

    # 終日の予定は dateTime を持たず date だけになる
    starts_at = start.get("dateTime", start.get("date"))
    ends_at = end.get("dateTime", end.get("date"))
    identifier = item.get("id")

    # 開始か終了が無い予定は画面に描けない。null を返さず落として非 null を保証する
    if not (identifier and starts_at and ends_at):
        return None

    return CalendarEvent(
        id=identifier,
        title=item.get("summary", NO_TITLE),
        description=item.get("description", ""),
        location=item.get("location", ""),
        start=starts_at,
        end=ends_at,
        html_link=item.get("htmlLink"),
        status=item.get("status"),
    )
