from langchain_core.runnables import Runnable
from loguru import logger

from app.llm.openai_gpt import chatgpt
from app.llm.sparring.prompts import PROMPT
from app.llm.sparring.schema import SlotFill
from app.schema import PlanDraft, SlotCode, SlotState, SparringResponse
from app.sparring.slots import CAUSAL_SLOTS, EFFECTS, FOLLOW_UPS, HINTS, QUESTIONS, RETRY_SLOTS, SLOT_ORDER

_chain: Runnable[dict[str, str], SlotFill] = PROMPT | chatgpt.with_structured_output(SlotFill)


def has_value(draft: PlanDraft, code: SlotCode) -> bool:
    """値が入っているか判定する。

    Args:
        draft: 現在のイベント内容。
        code: 判定するスロット。

    Returns:
        値があれば True。
    """
    if code == "partner":
        return bool(draft.partner)
    return getattr(draft, code) is not None


def is_done(draft: PlanDraft, code: SlotCode) -> bool:
    """もう聞かなくてよいか判定する。値が入ったか, 該当なしと答えられたか。

    Args:
        draft: 現在のイベント内容。
        code: 判定するスロット。

    Returns:
        聞き終わっていれば True。
    """
    return has_value(draft, code) or code in draft.skipped


def next_slot(draft: PlanDraft) -> SlotCode | None:
    """次に聞くスロットを返す。順序は実測に基づき固定(slots.py 参照)。

    Args:
        draft: 現在のイベント内容。

    Returns:
        未了のうち最も優先度が高いスロット。全て済んでいれば None。
    """
    return next((code for code in SLOT_ORDER if not is_done(draft, code)), None)


def slot_states(draft: PlanDraft) -> list[SlotState]:
    """画面に出すチェックリストを組み立てる。

    Args:
        draft: 現在のイベント内容。

    Returns:
        SLOT_ORDER の順に並んだ状態。
    """
    return [
        SlotState(
            code=code,
            label=QUESTIONS[code],
            filled=has_value(draft, code),
            skipped=code in draft.skipped,
            effect=EFFECTS[code],
            tone="causal" if code in CAUSAL_SLOTS else "functional",
        )
        for code in SLOT_ORDER
    ]


def merge_fill(draft: PlanDraft, fill: SlotFill) -> PlanDraft:
    """読み取れた値を未入力の項目にだけ写す。

    Args:
        draft: 現在のイベント内容。
        fill: 返答から読み取れたもの。

    Returns:
        更新後のイベント内容。
    """
    updated = draft.model_copy(deep=True)
    for code in SLOT_ORDER:
        value = getattr(fill, code)
        if value in (None, [], "") or has_value(updated, code):  # 既に埋まっている項目は上書きしない
            continue
        setattr(updated, code, value)
    return updated


def settle_reply(draft: PlanDraft, fill: SlotFill, asked: SlotCode, reply: str) -> PlanDraft:
    """1問ぶんの読み取り結果を反映する。LLM を呼ばない純粋部分。

    Args:
        draft: 現在のイベント内容。
        fill: 返答から読み取れたもの。
        asked: 直前に聞いたスロット。
        reply: 顧客の返答。ログにだけ使う。

    Returns:
        更新後のイベント内容。
    """
    updated = merge_fill(draft, fill)
    skipped = set(updated.skipped)
    retried = set(updated.retried)

    # 明示的に「無い」「決まっていない」と答えた項目は聞き終わりにする。値が入った項目は対象外
    skipped |= {code for code in fill.unavailable if not has_value(updated, code)}

    # 返答は直前に聞いた項目についてのものなので, 明示された分以外を勝手に打ち切らない
    if not has_value(updated, asked) and asked not in skipped:
        if asked in RETRY_SLOTS and asked not in retried:
            logger.info("聞き直す slot={} vague={} reply={}", asked, asked in fill.too_vague, reply)
            retried.add(asked)
        else:
            logger.info("読み取れず打ち切り slot={} reply={}", asked, reply)
            skipped.add(asked)
    updated.skipped = sorted(skipped)
    updated.retried = sorted(retried)
    return updated


def settle_form(draft: PlanDraft, fill: SlotFill, written: set[SlotCode]) -> PlanDraft:
    """フォーム一括の読み取り結果を反映する。LLM を呼ばない純粋部分。

    Args:
        draft: 現在のイベント内容。
        fill: 答え全体から読み取れたもの。
        written: 何か書かれていたスロット。空欄は該当なしとして扱う。

    Returns:
        更新後のイベント内容。
    """
    updated = merge_fill(draft, fill)
    retried = set(updated.retried)

    # 明示的に「無い」「決まっていない」と答えた項目は聞き直さず打ち切る
    unavailable = {code for code in fill.unavailable if not has_value(updated, code)}
    # 粗くて読み取れなかった項目は1回だけ聞き直す。2回目も読み取れなければ打ち切る
    vague = {
        code
        for code in written
        if code in RETRY_SLOTS and not has_value(updated, code) and code not in retried and code not in unavailable
    }
    updated.skipped = sorted({code for code in SLOT_ORDER if not has_value(updated, code)} - vague)
    updated.retried = sorted(retried | vague)
    return updated


async def apply_reply(draft: PlanDraft, asked: SlotCode, reply: str) -> PlanDraft:
    """返答を反映する。読み取れなかった項目は聞き直すか聞き終わり扱いにして先へ進む。

    Args:
        draft: 現在のイベント内容。
        asked: 直前に聞いたスロット。
        reply: 顧客の返答。

    Returns:
        更新後のイベント内容。
    """
    if not reply.strip():
        return draft

    fill = await _chain.ainvoke({"draft": draft.model_dump_json(), "question": QUESTIONS[asked], "reply": reply})
    return settle_reply(draft, fill, asked, reply)


async def fill_all(draft: PlanDraft, answers: dict[SlotCode, str]) -> PlanDraft:
    """フォームで一度に受けた答えをまとめて反映する。空欄は該当なしとして扱う。

    Args:
        draft: 現在のイベント内容。
        answers: スロットごとの自由記述。

    Returns:
        更新後のイベント内容。
    """
    written = {code: text.strip() for code, text in answers.items() if text.strip()}

    fill = SlotFill()
    if written:
        # 質問文を添えてどの答えがどの項目のものか分かるようにする。抽出側は複数項目に対応済み
        labelled = "\n".join(f"{QUESTIONS[code]} → {text}" for code, text in written.items())
        fill = await _chain.ainvoke({"draft": draft.model_dump_json(), "question": "(まとめて)", "reply": labelled})

    return settle_form(draft, fill, set(written))


async def step(draft: PlanDraft, reply: str) -> SparringResponse:
    """壁打ちを1往復進める。

    Args:
        draft: 現在のイベント内容。
        reply: 直前の質問への返答。初回は空。

    Returns:
        更新後の内容と, 次に聞くこと。
    """
    asked = next_slot(draft)
    updated = await apply_reply(draft, asked, reply) if asked else draft
    following = next_slot(updated)
    # 聞き直し中の項目には, 粒度を下げた別の言い方を出す
    question = None
    if following:
        retrying = following in updated.retried and not has_value(updated, following)
        question = FOLLOW_UPS[following] if retrying and following in FOLLOW_UPS else QUESTIONS[following]
    return SparringResponse(
        draft=updated,
        question=question,
        hint=HINTS[following] if following else None,
        slots=slot_states(updated),
        ready=following is None,
    )
