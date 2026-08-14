from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

# expires_at と Cookie の max-age をこの1つから導く
SESSION_EXPIRY_DAYS = 7

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
    page_view: int = Field(default=0, description="閲覧数。顧客には出さない。評価に使う生値")
    regional_reach: int = Field(default=0, description="lift>=5 の媒体の数。地元に届いたか")
    pv_score: float = Field(default=0.0, description="公開月内のパーセンタイル。生の PV は月で43倍動くので均す")
    regional_score: float = Field(default=0.0, description="県内のパーセンタイル。県で勝率4%〜83%の差が出るので均す")
    embedding: Any = Field(sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=False))


class PrefectureWeight(SQLModel, table=True):
    """県ごとの地域メディアの厚み。地元を推してよいかの重みになる。"""

    __tablename__ = "prefecture_weight"  # pyright: ignore[reportAssignmentType]

    prefecture_id: int = Field(primary_key=True)
    regional_weight: float = Field(description="regional_reach の非ゼロ率。奈良0.26 / 東京0.18 / 山口1.00")


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


class User(SQLModel, table=True):
    """カレンダーを連携した人。壁打ちと提案は匿名のままなので, ここに入るのは連携した人だけ。"""

    __tablename__ = "users"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str | None = Field(default=None, max_length=320, description="Google から得たメールアドレス")
    name: str = Field(default="", max_length=255, description="Google から得た表示名")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OAuthIdentity(SQLModel, table=True):
    """外部 IdP のアカウント。provider と subject の組で1人を指す。"""

    __tablename__ = "oauth_identities"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_provider_subject"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    provider: str = Field(max_length=50, description="google など")
    subject: str = Field(max_length=255, description="プロバイダ内での一意なID")
    email: str | None = Field(default=None, max_length=320)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class UserSession(SQLModel, table=True):
    """ログインを保つためのセッション。生のトークンは保存せずハッシュだけ持つ。"""

    __tablename__ = "user_sessions"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    token_hash: str = Field(max_length=64, unique=True, description="Cookie の値の SHA-256")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC) + timedelta(days=SESSION_EXPIRY_DAYS),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="連携を切ったら入る。アクティブなら null",
    )
    user_agent: str | None = Field(default=None, max_length=512)
    ip_address: str | None = Field(default=None, max_length=45)


class Event(SQLModel, table=True):
    """このアプリが持つ予定。Google から読んだものも採点のためここに写す。"""

    __tablename__ = "events"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("user_id", "external_id", name="uq_events_user_external"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    source: str = Field(default="self", max_length=16, description="self か google")
    external_id: str | None = Field(default=None, max_length=255, description="Google 側の予定ID。自作なら None")
    title: str = Field(max_length=255, description="予定の件名")
    description: str = Field(default="", description="予定の詳細。無ければ空文字")
    location: str = Field(default="", max_length=255, description="場所。無ければ空文字")
    starts_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="開始日時",
    )
    ends_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="終了日時",
    )
    all_day: bool = Field(default=False, description="終日の予定か。真なら画面には日付だけ出す")
    scored_text: str = Field(default="", description="採点に使った本文。変わったときだけ引き直す")
    embedding: Any = Field(default=None, sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=True))
    score: float | None = Field(default=None, description="似た事例がどれだけ届いたか。顧客には数値を出さない")
    # 壁打ちの答えを画面から切り離して持つ。ページを移っても聞き直さない
    draft: dict[str, object] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class GoogleCredential(SQLModel, table=True):
    """Google が発行したカレンダー用のトークン。1ユーザーに1つ。"""

    __tablename__ = "google_credentials"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", unique=True, index=True)
    token_json: str = Field(description="Credentials.to_json() の中身。refresh のたびに書き戻す")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=lambda: datetime.now(UTC)),
    )
