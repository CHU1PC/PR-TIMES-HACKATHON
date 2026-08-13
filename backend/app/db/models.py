from datetime import date
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

# app/llm/embeddings.py の DIMENSIONS と必ず揃える。ずれると投入時に落ちる
EMBEDDING_DIMENSIONS = 256


class Corpus(SQLModel, table=True):
    """検索対象の過去リリース。ETL が選抜した12.9万件。"""

    __tablename__ = "corpus"  # pyright: ignore[reportAssignmentType]

    company_id: int = Field(primary_key=True, description="PR TIMES 側の企業ID")
    release_id: int = Field(primary_key=True, description="企業内でのリリースID")
    title: str = Field(description="リリースのタイトル")
    subtitle: str = Field(default="", description="サブタイトル。lead_paragraph の代替")
    body_head: str = Field(default="", description="本文冒頭をHTML除去して1000文字")
    company_name: str | None = Field(default=None)
    business_category_id: int | None = Field(default=None, index=True, description="加点の一致判定に使う")
    business_category_name: str | None = Field(default=None)
    release_type_name: str | None = Field(default=None)
    prefecture_id: int | None = Field(default=None, index=True, description="加点の一致判定に使う")
    prefecture_name: str | None = Field(default=None)
    city_name: str | None = Field(default=None)
    published_on: date = Field(description="配信日")
    reach: int = Field(description="転載したユニーク媒体数。顧客には出さない")
    reach_score: float = Field(description="log1p(reach)/log1p(max)。投入時に計算し毎クエリ再計算しない")
    embedding: Any = Field(sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=False))


class CorpusMedia(SQLModel, table=True):
    """どの事例をどの媒体が拾ったか。1事例あたり約47行。"""

    __tablename__ = "corpus_media"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(index=True)
    release_id: int = Field(index=True)
    new_site_name: str = Field(index=True)


class MediaFrequency(SQLModel, table=True):
    """媒体ごとの出現事例数。全国メディアと地方紙を分ける唯一の手掛かり。"""

    __tablename__ = "media_frequency"  # pyright: ignore[reportAssignmentType]

    new_site_name: str = Field(primary_key=True)
    case_count: int = Field(description="この媒体が出てくる事例の数")


class MediaTotal(SQLModel, table=True):
    """media_frequency の分母。1行だけ持つ。"""

    __tablename__ = "media_total"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    case_count: int = Field(description="媒体情報のある事例の総数")


class Place(SQLModel, table=True):
    """地名から都道府県IDを引くための索引。"""

    __tablename__ = "places"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True, description="'prefecture' か 'city'")
    name: str
    prefecture_id: int


class Category(SQLModel, table=True):
    """コーパスに事例がある業種。LLM にはこの一覧からだけ選ばせる。"""

    __tablename__ = "categories"  # pyright: ignore[reportAssignmentType]

    business_category_id: int = Field(primary_key=True)
    business_category_name: str
