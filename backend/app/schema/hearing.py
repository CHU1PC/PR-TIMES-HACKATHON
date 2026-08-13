from pydantic import BaseModel, Field

from app.schema.plan import PlanCategory


class Exchange(BaseModel):
    """聞き取りの1往復。"""

    question: str = Field(description="こちらが聞いたこと")
    answer: str = Field(description="相手の返答")


class HearingTurn(BaseModel):
    """1往復ぶんの入力。"""

    history: list[Exchange] = Field(default_factory=list[Exchange], description="ここまでの往復。初回は空")
    answer: str = Field(default="", description="直前の質問への返答。初回は空")


class Candidate(BaseModel):
    """回答から抽出した予定候補。"""

    title: str = Field(description="予定として登録する一文")
    category: PlanCategory = Field(description="requirements §6.2 の8分類")
    source: str = Field(description="根拠になった回答の引用")
    reason: str = Field(description="なぜ発信できるかを1行で")


class HearingResponse(BaseModel):
    """1往復ぶんの応答。"""

    history: list[Exchange] = Field(description="返答を追加した後の往復履歴")
    question: str | None = Field(default=None, description="次に聞くこと。聞き終わったら None")
    hint: str | None = Field(default=None, description="答えやすくするための例示")
    candidates: list[Candidate] = Field(description="ここまでに見つかった予定候補")
    done: bool = Field(description="聞き終わったか")
