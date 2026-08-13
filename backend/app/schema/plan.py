from typing import Literal

from pydantic import BaseModel, Field

Phase = Literal["before", "onday", "after"]
Tone = Literal["causal", "functional"]
Disclosure = Literal["ok", "ng", "unknown"]
ChecklistCode = Literal["A", "B", "C", "D", "E", "F"]
Presence = Literal["yes", "no", "unknown"]

# requirements §6.2 の8分類。イベントに限定しないことで, 催しを開けない企業も 4・5・7 だけで運用できる
PlanCategory = Literal[
    "販売・提供の開始/拡大",
    "提携・連携の開始",
    "場所・チャネルの追加",
    "商品・サービスの改訂",
    "人・組織の変化",
    "受賞・認定",
    "数字の節目",
    "外部イベント出展",
]


class Actor(BaseModel):
    """予定に登場する社外の相手先。"""

    name: str = Field(description="社外の相手先の名前")
    disclosure: Disclosure = Field(default="unknown", description="名前を掲載してよいか")


class PlanCreate(BaseModel):
    """顧客が入力した1件の予定。"""

    company_id: int = Field(description="PR TIMES 側の企業ID")
    title: str = Field(description="これから決まっていること・変わることを1行で")
    category: PlanCategory | None = Field(default=None, description="requirements §6.2 の8分類")
    start_date: str | None = Field(default=None, description="開始日 YYYY-MM-DD。未定なら None")
    date_fixed: bool = Field(default=False, description="開始日が確定しているか")
    actors: list[Actor] = Field(default_factory=list[Actor], description="社外の相手。空なら社内のみ")
    people_present: Presence | None = Field(default=None, description="当日その場に人がいるか")
    location: str | None = Field(default=None, description="市区町村まで。オンライン可")
    goal: str | None = Field(default=None, description="この予定で一番うれしいこと")


class PlanCreated(BaseModel):
    """登録された予定の識別子。"""

    plan_id: str = Field(description="以降の参照に使う識別子")


class ChecklistItem(BaseModel):
    """追加コスト0〜15分で足せる要素1つ。"""

    code: ChecklistCode = Field(description="requirements §6.5 の項目記号")
    label: str = Field(description="顧客に見せる項目名")
    tone: Tone = Field(description="causal は判定クエリC を通った項目のみ。既定は functional")
    done: bool = Field(default=False, description="入力済みの情報から自動で満たせているか")


class Angle(BaseModel):
    """1つの予定を分解した3枠のうちの1枠。"""

    phase: Phase = Field(description="before / onday / after")
    subject: str = Field(description="その回の主語")
    message: str = Field(description="何を伝える回か")
    audience_label: str = Field(description="だれに届く回か。露出数は書かない")
    publish_offset_days: int = Field(description="開始日からの相対日")
    publish_date: str | None = Field(default=None, description="開始日が確定している場合の配信日")
    effort: str = Field(description="所要時間と費用")
    checklist: list[ChecklistItem] = Field(description="この枠で足せる要素")
    draft_text: str = Field(default="", description="原稿ドラフト全文")
    request_email: str | None = Field(default=None, description="相手先への依頼メール文面")


class PlanResult(BaseModel):
    """予定と, そこから展開した3枠。"""

    plan: PlanCreate = Field(description="入力された予定")
    angles: list[Angle] = Field(description="必ず3件。1枠も空にしない")
