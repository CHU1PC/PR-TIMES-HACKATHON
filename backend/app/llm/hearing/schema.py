from pydantic import BaseModel, Field

from app.schema import PlanCategory


class ExtractedPlan(BaseModel):
    """回答から抽出した予定候補1件。"""

    title: str = Field(description="予定として登録する一文。回答に無いことを足さない。助詞を落とさない")
    category: PlanCategory = Field(description="requirements §6.2 の8分類のいずれか")
    source: str = Field(description="根拠になった回答の引用。原文をそのまま抜く")
    reason: str = Field(description="なぜ発信できるかを1行で。効果・数値・こちらへの指示は書かない")


class HearingStep(BaseModel):
    """1往復ぶんの判断。次に聞くことと, ここまでに拾えた候補。"""

    question: str | None = Field(
        default=None,
        description="次に聞く質問。すでにやっていることだけを聞く。提案はしない。聞き終わったら None",
    )
    hint: str | None = Field(default=None, description="答えやすくする例示を短く。不要なら None")
    candidates: list[ExtractedPlan] = Field(description="ここまでの往復から拾えた候補。最大4件。無ければ空")
    done: bool = Field(description="候補が十分に集まった, またはこれ以上聞いても出てこないなら真")
