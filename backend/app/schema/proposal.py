from pydantic import BaseModel, Field

from app.schema.sparring import PlanDraft


class ProposalCase(BaseModel):
    """コーパスから引いた過去の1件。reach は顧客画面に出さない(requirements §7)。

    出すのは取り組みのやり方だけなので, 他社を名指しできる情報は exclude=True で JSON に載せない。
    タイトルと本文は社名を含むことが多く, LLM には渡すが応答には出さない。
    """

    company_id: int = Field(exclude=True, description="PR TIMES 側の企業ID")
    release_id: int = Field(exclude=True, description="企業内でのリリースID")
    title: str = Field(exclude=True, description="リリースのタイトル")
    subtitle: str = Field(default="", exclude=True, description="サブタイトル。lead_paragraph の代替")
    body_head: str = Field(default="", exclude=True, description="本文冒頭をHTML除去して1000文字")
    company_name: str | None = Field(default=None, exclude=True, description="配信企業名")
    business_category: str | None = Field(default=None, description="業種名")
    release_type: str | None = Field(default=None, description="リリース種別名")
    prefecture: str | None = Field(default=None, description="都道府県名")
    city: str | None = Field(default=None, description="市区町村名")
    published_on: str = Field(description="配信日 YYYY-MM-DD")

    # exclude=True で JSON に載せない。応答に含めると画面に出す余地が残る(requirements §7)
    reach: int = Field(exclude=True, description="転載したユニーク媒体数。並び替えにだけ使う")
    similarity: float = Field(exclude=True, description="クエリとのコサイン類似度。並び替えにだけ使う")
    media: list[str] = Field(description="この事例を拾った媒体のうち特徴的なもの")


class Suggestion(BaseModel):
    """顧客に見せる提案1件。"""

    action: str = Field(description="この取り組みに足すこと。1文の命令形にしない, 提案の形にする")
    reason: str = Field(description="なぜそれが効くか。事例に即して書く")
    cited: list[int] = Field(
        # release_id は企業をまたいで重複する(実測3,352個)ので指し先に使えない
        description="根拠にした事例。cases 配列の位置を指す0始まりの添字",
    )


class ProposalRequest(BaseModel):
    """提案の入力。壁打ちが完了した draft をそのまま渡す。"""

    draft: PlanDraft = Field(description="壁打ちで埋めたイベント内容")


class ProposalResponse(BaseModel):
    """提案の出力。"""

    suggestions: list[Suggestion] = Field(description="足せること。3件")
    cases: list[ProposalCase] = Field(description="根拠にした事例")
    media: list[str] = Field(
        description="事例群を拾っていた媒体のうち特徴的なもの。件数は付けない(requirements §7)",
    )
