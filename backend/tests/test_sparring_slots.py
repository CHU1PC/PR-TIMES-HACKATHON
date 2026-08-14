import asyncio

import pytest

from app.llm.sparring.schema import SlotFill
from app.schema import PlanDraft, SlotCode
from app.sparring.core import has_value, is_done, next_slot, settle_form, settle_reply, slot_states, step
from app.sparring.slots import CAUSAL_SLOTS, FOLLOW_UPS, SLOT_ORDER


def draft(**kwargs: object) -> PlanDraft:
    """テスト用の予定を作る。指定しない項目は未入力のまま。

    Args:
        kwargs: 埋めておきたい項目。

    Returns:
        PlanDraft。
    """
    return PlanDraft(title="来月から直販を始めます", **kwargs)


def test_place_is_asked_first() -> None:
    """効果量が最大の place を最初に聞く(docs/findings.md §4)。"""
    assert next_slot(draft()) == "place"
    assert SLOT_ORDER[0] == "place"


def test_filled_slot_advances() -> None:
    """値が入った項目は聞き直さない。"""
    assert next_slot(draft(place="熊本市中央区")) == "partner"


def test_skipped_slot_advances() -> None:
    """該当なしと答えた項目も聞き直さない。これが無いと同じ質問を繰り返す。"""
    assert next_slot(draft(skipped=["place"])) == "partner"


@pytest.mark.parametrize("code", SLOT_ORDER)
def test_every_slot_terminates(code: SlotCode) -> None:
    """どの項目も, 値が入るか該当なしになれば必ず先へ進む。"""
    assert not is_done(draft(), code)
    assert is_done(draft(skipped=[code]), code)


def test_partner_needs_a_non_empty_list() -> None:
    """Partner は空リストだと未入力。他の項目の None 判定と扱いが違う。"""
    assert not has_value(draft(partner=[]), "partner")
    assert has_value(draft(partner=["郵便局"]), "partner")


def test_all_done_returns_none() -> None:
    """全項目が済んだら聞くことが無くなる。"""
    assert next_slot(draft(skipped=list(SLOT_ORDER))) is None


def test_only_place_claims_causality() -> None:
    """判定クエリC を通った項目だけ causal。他は機能説明に留める(§6.5)。"""
    tones = {s.code: s.tone for s in slot_states(draft())}
    assert tones["place"] == "causal"
    assert {code for code, tone in tones.items() if tone == "causal"} == set(CAUSAL_SLOTS)


def test_effects_never_promise_numbers() -> None:
    """顧客に見せる文言に数値の予測や効果の断定を含めない(制約1・3)。"""
    forbidden = ("%", "％", "倍", "スコア", "点", "予測", "増えます", "見込め")
    for state in slot_states(draft()):
        assert not any(word in state.effect for word in forbidden), state.effect


def test_form_vague_place_is_retried_once() -> None:
    """粗い地名は skipped でなく retried に積み, 同じ項目を聞き直す(B-1)。"""
    updated = settle_form(draft(), SlotFill(too_vague=["place"]), {"place"})
    assert updated.retried == ["place"]
    assert "place" not in updated.skipped
    assert next_slot(updated) == "place"


def test_form_retry_question_uses_follow_up() -> None:
    """聞き直しでは粒度を下げた FOLLOW_UPS の文言を出す。"""
    updated = settle_form(draft(), SlotFill(), {"place"})
    response = asyncio.run(step(updated, ""))
    assert response.question == FOLLOW_UPS["place"]


def test_form_vague_place_gives_up_on_second_try() -> None:
    """2回目も読み取れなければ打ち切って先へ進む(requirements §6.1)。"""
    updated = settle_form(draft(retried=["place"]), SlotFill(), {"place"})
    assert "place" in updated.skipped
    assert next_slot(updated) is None


def test_form_unavailable_is_not_retried() -> None:
    """「まだ決まっていません」は粗い入力でなく該当なし。聞き直さない(B-2)。"""
    updated = settle_form(draft(), SlotFill(unavailable=["place"]), {"place"})
    assert "place" in updated.skipped
    assert updated.retried == []


def test_form_unavailable_does_not_erase_value() -> None:
    """値が読み取れた項目は unavailable に入っていても入力扱いのまま。"""
    updated = settle_form(draft(), SlotFill(place="熊本市", unavailable=["place"]), {"place"})
    assert updated.place == "熊本市"
    assert "place" not in updated.skipped


def test_form_blank_answers_skip_everything() -> None:
    """空欄は該当なし。何も書かなければ全項目が聞き終わりになる。"""
    updated = settle_form(draft(), SlotFill(), set())
    assert set(updated.skipped) == set(SLOT_ORDER)
    assert updated.retried == []


def test_reply_unavailable_skips_the_slot() -> None:
    """1問ずつの往復でも, 明示的な「無い」は該当なしとして次へ進む(B-2)。"""
    updated = settle_reply(draft(), SlotFill(unavailable=["place"]), "place", "まだ決まっていません")
    assert "place" in updated.skipped
    assert updated.retried == []
    assert next_slot(updated) == "partner"


def test_reply_unavailable_covers_mentioned_slots() -> None:
    """返答で明示的に触れた別の項目も該当なしにする。値が入った項目は消さない。"""
    fill = SlotFill(partner=["郵便局"], unavailable=["video"])
    updated = settle_reply(draft(place="熊本市中央区"), fill, "partner", "郵便局さんと。動画はありません")
    assert updated.partner == ["郵便局"]
    assert "video" in updated.skipped
    assert "place" not in updated.skipped
