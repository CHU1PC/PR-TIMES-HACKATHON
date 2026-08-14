from typing import Literal

from pydantic import BaseModel, Field

SlotCode = Literal["place", "partner", "people", "novelty", "observation", "video"]


class SlotFill(BaseModel):
    """返答から読み取れたもの。返答に無い項目は None のまま返す。"""

    place: str | None = Field(
        default=None,
        description="地名. 市区町村なら「熊本市中央区」, 都道府県だけなら「山梨県」, オンラインなら「オンライン」",
    )
    partner: list[str] = Field(default_factory=list[str], description="社外で関わる相手の名前")
    people: Literal["yes", "no", "unknown"] | None = Field(default=None, description="当日その場に人がいるか")
    novelty: str | None = Field(default=None, description="御社として初めてのこと")
    observation: str | None = Field(default=None, description="当日見聞きできそうなこと")
    video: Literal["yes", "no"] | None = Field(default=None, description="すでにある動画の有無")

    unavailable: list[SlotCode] = Field(
        default_factory=list[SlotCode],
        description="相手が明示的に「無い」「いない」「決まっていない」と答えた項目のみ。話題に出ていない項目は入れない",
    )
    too_vague: list[SlotCode] = Field(
        default_factory=list[SlotCode],
        description="答えはあったが粒度が足りず埋められない項目。例: 地名が「関東」だけ。聞き直す対象になる",
    )
