from pydantic import BaseModel, Field

from app.schema import SlotCode


class CategoryPick(BaseModel):
    """予定をコーパスの業種に当てた結果。"""

    business_category_name: str | None = Field(
        default=None,
        description="渡した一覧の中から最も近いものを1つ。どれにも当たらなければ None",
    )


class DraftSuggestion(BaseModel):
    """事例から引き出した, 予定に足せること1件。"""

    borrowed: str = Field(
        description="cited した事例に実際に出てくる普通名詞を1つそのまま。場所の種類・人の種類・モノ。"
        "「施設」「関係者」のような一般語と、会社名・店名・商品名などの固有名詞は入れない",
    )
    action: str = Field(
        description="borrowed をそのまま使ってこの予定に足すこと。20〜60字。命令形にせず提案の形で書く。"
        "顧客がそのまま読む文にする。他社名とスロット名は書かない",
    )
    reason: str = Field(
        description="事例のどこから言えるのか。事例に書かれていたことだけを根拠にする。他社名は書かずやり方で書く",
    )
    addresses: SlotCode | None = Field(
        default=None,
        description="この提案が埋める未定の項目。未定を埋めるものでなければ None",
    )
    # release_id は企業をまたいで重複する(実測3,352個)ので, 事例の指し先には使えない
    cited: list[int] = Field(
        default_factory=list[int],
        description="根拠にした事例の番号。渡した #1〜#8 の数字。1件以上必ず入れる",
    )


class SuggestionSet(BaseModel):
    """1回の提案。"""

    suggestions: list[DraftSuggestion] = Field(description="足せること。3件。互いに重ならないものにする")
