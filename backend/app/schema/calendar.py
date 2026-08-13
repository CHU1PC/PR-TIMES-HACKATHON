from pydantic import BaseModel, ConfigDict, Field


class EventQuery(BaseModel):
    """予定を引く期間。キーは Google Calendar API の名前に合わせる。"""

    time_min: str | None = Field(default=None, alias="timeMin", description="取得開始時刻 (RFC3339)")
    time_max: str | None = Field(default=None, alias="timeMax", description="取得終了時刻 (RFC3339)")


class CalendarEvent(BaseModel):
    """カレンダーの予定1件。"""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Google 側の予定ID")
    title: str = Field(description="予定の件名。無題なら (タイトルなし)")
    description: str = Field(default="", description="予定の詳細")
    location: str = Field(default="", description="場所")
    start: str = Field(description="開始。終日予定は日付だけになる")
    end: str = Field(description="終了。終日予定は日付だけになる")
    html_link: str | None = Field(default=None, alias="htmlLink", description="Google カレンダーで開く URL")
    status: str | None = Field(default=None, description="confirmed / tentative / cancelled")


class CalendarStatus(BaseModel):
    """連携しているかどうか。"""

    configured: bool = Field(description="この環境で連携機能が使えるか。false なら連携ボタンを出さない")
    connected: bool = Field(description="Google と連携済みか")


class CalendarEvents(BaseModel):
    """指定期間の予定。"""

    connected: bool = Field(description="Google と連携済みか")
    events: list[CalendarEvent] = Field(default_factory=list[CalendarEvent], description="期間内の予定")
