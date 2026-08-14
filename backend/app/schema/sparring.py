from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

SlotCode = Literal["place", "partner", "people", "novelty", "observation", "video"]

# 顧客の自由記述はここまで。上限が無いとプロンプトへ無制限に増幅される
REPLY_MAX = 2000

Reply = Annotated[str, StringConstraints(max_length=REPLY_MAX)]


class PlanDraft(BaseModel):
    """壁打ちで育てている途中のイベント内容。"""

    title: str = Field(description="これからやることを1行で")
    start_date: str | None = Field(default=None, description="開始日 YYYY-MM-DD。未定なら None")
    place: str | None = Field(default=None, description="市区町村または都道府県。オンライン可")
    partner: list[str] = Field(default_factory=list[str], description="社外で関わる相手の名前")
    people: Literal["yes", "no", "unknown"] | None = Field(default=None, description="当日その場に人がいるか")
    novelty: str | None = Field(default=None, description="御社として初めてのこと")
    observation: str | None = Field(default=None, description="当日見聞きできそうなこと")
    video: Literal["yes", "no"] | None = Field(default=None, description="すでにある動画の有無")

    skipped: list[SlotCode] = Field(
        default_factory=list[SlotCode],
        description="聞いたが該当が無かった項目。同じ質問を繰り返さないために覚えておく",
    )
    retried: list[SlotCode] = Field(
        default_factory=list[SlotCode],
        description="読み取れず聞き直した項目。2回目で読み取れなければ skipped へ送る",
    )


class SparringTurn(BaseModel):
    """1往復ぶんの入力。"""

    draft: PlanDraft = Field(description="いま分かっているイベント内容")
    reply: Reply = Field(default="", description="直前の質問への顧客の返答。初回は空")


class SparringForm(BaseModel):
    """フォームで一度に受け取る答え。空欄の項目は該当なしとして扱う。"""

    draft: PlanDraft = Field(description="いま分かっているイベント内容")
    answers: dict[SlotCode, Reply] = Field(
        default_factory=dict[SlotCode, Reply],
        description="スロットごとの自由記述。書かなかった項目は入れなくてよい",
    )


class SlotState(BaseModel):
    """1スロットの状態。画面のチェックリストになる。"""

    code: SlotCode = Field(description="スロット識別子")
    label: str = Field(description="顧客に見せる質問文")
    filled: bool = Field(description="値が入っているか")
    skipped: bool = Field(description="聞いたが該当が無かったか")
    effect: str = Field(description="埋まると何が起きるか。数値と効果の断定は書かない")
    tone: Literal["causal", "functional"] = Field(description="causal は判定クエリC を通ったスロットのみ")


class SparringResponse(BaseModel):
    """1往復ぶんの応答。"""

    draft: PlanDraft = Field(description="返答を反映した後のイベント内容")
    question: str | None = Field(description="次に聞くこと。全部済んだら None")
    hint: str | None = Field(description="答えやすくするための例示")
    slots: list[SlotState] = Field(description="チェックリスト。SLOT_ORDER の順に並ぶ")
    ready: bool = Field(description="出せる形になったか")
