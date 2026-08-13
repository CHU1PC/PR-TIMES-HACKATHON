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
    description: str = Field(description="予定の詳細。無ければ空文字")
    location: str = Field(description="場所。無ければ空文字")
    start: str = Field(description="開始。終日予定は日付だけになる")
    end: str = Field(description="終了。終日予定は日付だけになる")
    html_link: str | None = Field(alias="htmlLink", description="Google カレンダーで開く URL")
    status: str | None = Field(description="confirmed / tentative / cancelled")


class CalendarStatus(BaseModel):
    """ログインと連携の状況。"""

    signed_in: bool = Field(description="ログイン済みか。予定を引けるかはこれで決まる")
    configured: bool = Field(description="この環境で Google 連携が使えるか。false なら連携ボタンを出さない")
    connected: bool = Field(description="Google と連携済みか。デモでログインしただけなら false")
    demo: bool = Field(description="Google なしのデモログインを開いているか。false ならボタンを出さない")


class EventCreate(BaseModel):
    """画面から足す予定1件。時刻は RFC3339 で受ける。"""

    title: str = Field(min_length=1, max_length=255, description="予定の件名")
    description: str = Field(default="", description="予定の詳細。無ければ空文字")
    all_day: bool = Field(default=False, alias="allDay", description="終日の予定か")
    starts_at: str = Field(alias="startsAt", description="開始 (RFC3339)")
    ends_at: str = Field(alias="endsAt", description="終了 (RFC3339)")

    model_config = ConfigDict(populate_by_name=True)


class DemoLogin(BaseModel):
    """デモでログインする人。名前だけで identity を作る。"""

    name: str | None = Field(default=None, description="表示名。空なら既定の名前を使う")


class CalendarEvents(BaseModel):
    """指定期間の予定。"""

    connected: bool = Field(description="Google と連携済みか。デモでログインしただけなら false")
    events: list[CalendarEvent] = Field(description="期間内の予定。Google の分と自分で足した分の両方")
