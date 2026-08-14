from datetime import datetime, timedelta, timezone

from app.calendar.scoring import DESCRIPTION_CHARS, parse_moment, scored_text

JST = timezone(timedelta(hours=9))


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
