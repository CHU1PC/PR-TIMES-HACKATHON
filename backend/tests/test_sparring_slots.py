import pytest

from app.schema import PlanDraft, SlotCode
from app.sparring.core import has_value, is_done, next_slot, slot_states
from app.sparring.slots import CAUSAL_SLOTS, SLOT_ORDER


def draft(**kwargs: object) -> PlanDraft:
    """テスト用の予定を作る。指定しない項目は未入力のまま。

    Args:
        kwargs: 埋めておきたい項目。

    Returns:
        PlanDraft。
    """
    return PlanDraft(title="来月から直販を始めます", **kwargs)


def test_place_is_asked_first() -> None:
    """効果量が最大の place を最初に聞く（docs/findings.md §4）。"""
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
    """判定クエリC を通った項目だけ causal。他は機能説明に留める（§6.5）。"""
    tones = {s.code: s.tone for s in slot_states(draft())}
    assert tones["place"] == "causal"
    assert {code for code, tone in tones.items() if tone == "causal"} == set(CAUSAL_SLOTS)


def test_effects_never_promise_numbers() -> None:
    """顧客に見せる文言に数値の予測や効果の断定を含めない（制約1・3）。"""
    forbidden = ("%", "％", "倍", "スコア", "点", "予測", "増えます", "見込め")
    for state in slot_states(draft()):
        assert not any(word in state.effect for word in forbidden), state.effect
