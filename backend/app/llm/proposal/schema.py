from pydantic import BaseModel, Field


class CategoryPick(BaseModel):
    """予定をコーパスの業種に当てた結果。"""

    business_category_name: str | None = Field(
        default=None,
        description="渡した一覧の中から最も近いものを1つ。どれにも当たらなければ None",
    )


class DraftSuggestion(BaseModel):
    """事例から引き出した, 予定に足せること1件。"""

    action: str = Field(description="この予定に足すこと。20〜60字。命令形にせず提案の形で書く")
    reason: str = Field(description="事例のどこから言えるのか。事例に書かれていたことだけを根拠にする")
    # release_id は企業をまたいで重複する(実測3,352個)ので, 事例の指し先には使えない
    cited: list[int] = Field(
        default_factory=list[int],
        description="根拠にした事例の番号。渡した #1〜#8 の数字。1件以上必ず入れる",
    )


class SuggestionSet(BaseModel):
    """1回の提案。"""

    suggestions: list[DraftSuggestion] = Field(description="足せること。3件。互いに重ならないものにする")
