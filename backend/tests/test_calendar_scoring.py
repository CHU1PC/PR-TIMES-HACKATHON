from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.calendar.scoring import (
    DESCRIPTION_CHARS,
    LOCATION_CHARS,
    TITLE_CHARS,
    parse_moment,
    scored_text,
    sync_updates,
    sync_values,
)
from app.schema.calendar import CalendarEvent

JST = timezone(timedelta(hours=9))


def _event(title: str = "件名", location: str = "") -> CalendarEvent:
    """テスト用の Google 予定を1件組む。

    Args:
        title: 予定の件名。
        location: 場所。

    Returns:
        予定1件。
    """
    return CalendarEvent(
        id="evt-1",
        title=title,
        description="",
        location=location,
        start="2026-08-14",
        end="2026-08-15",
        html_link=None,
        status="confirmed",
        score=None,
        draft=None,
    )


def test_location_is_part_of_the_scored_text() -> None:
    """地域情報は実測で効果が確認できている唯一の項目なので採点本文に入れる(docs/findings.md §4)。"""
    assert "熊本市中央区" in scored_text("直販を始めます", "熊本市中央区", "9月から")


def test_empty_fields_are_dropped() -> None:
    """未入力の項目で空行を作らない。"""
    assert scored_text("直販を始めます", "", "") == "直販を始めます"


def test_long_description_is_cut() -> None:
    """詳細は長いことがある。採点に効くのは冒頭だけ。"""
    text = scored_text("件名", "", "あ" * (DESCRIPTION_CHARS + 100))
    assert len(text) == len("件名") + 1 + DESCRIPTION_CHARS


def test_all_day_date_gets_a_timezone() -> None:
    """終日の予定は日付だけで来る。素のまま入れると timestamptz に落ちる。"""
    assert parse_moment("2026-08-14", JST) == datetime(2026, 8, 14, tzinfo=JST)


def test_existing_timezone_is_kept() -> None:
    """時刻つきの予定は Google が付けた時間帯を上書きしない。"""
    assert parse_moment("2026-08-14T10:00:00+00:00", JST).utcoffset() == timedelta(0)


def test_title_at_the_column_limit_is_kept() -> None:
    """255字ちょうどは列に収まるので切らない。"""
    values = sync_values(uuid4(), _event(title="あ" * TITLE_CHARS), JST)
    assert values["title"] == "あ" * TITLE_CHARS


def test_overlong_title_is_cut_to_the_column() -> None:
    """256字は VARCHAR(255) を超え, 切らないと取り込みが落ち続ける。"""
    values = sync_values(uuid4(), _event(title="あ" * (TITLE_CHARS + 1)), JST)
    assert values["title"] == "あ" * TITLE_CHARS


def test_overlong_location_is_cut_to_the_column() -> None:
    """場所も同じ桁で切る。"""
    values = sync_values(uuid4(), _event(location="あ" * (LOCATION_CHARS + 1)), JST)
    assert values["location"] == "あ" * LOCATION_CHARS


def test_empty_location_is_not_written_back() -> None:
    """Google 側が空のとき, 壁打ちで埋めた場所を空で潰さない。"""
    updates = sync_updates(sync_values(uuid4(), _event(location=""), JST))
    assert "location" not in updates


def test_filled_location_overwrites() -> None:
    """Google 側に場所があればそちらを正とする。"""
    updates = sync_updates(sync_values(uuid4(), _event(location="熊本市中央区"), JST))
    assert updates["location"] == "熊本市中央区"
