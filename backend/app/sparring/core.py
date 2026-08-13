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


async def apply_reply(draft: PlanDraft, asked: SlotCode, reply: str) -> PlanDraft:
    """返答を反映する。読み取れなかった項目は聞き終わり扱いにして先へ進む。

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
    updated = draft.model_copy(deep=True)
    for code in SLOT_ORDER:
        value = getattr(fill, code)
        if value in (None, [], "") or has_value(updated, code):  # 既に埋まっている項目は上書きしない
            continue
        setattr(updated, code, value)

    # 返答は直前に聞いた項目についてのものなので, それ以外を勝手に打ち切らない
    skipped = set(updated.skipped)
    retried = set(updated.retried)
    if not has_value(updated, asked):
        if asked in RETRY_SLOTS and asked not in retried:
            logger.info("聞き直す slot={} vague={} reply={}", asked, asked in fill.too_vague, reply)
            retried.add(asked)
        else:
            logger.info("読み取れず打ち切り slot={} reply={}", asked, reply)
            skipped.add(asked)
    updated.skipped = sorted(skipped)
    updated.retried = sorted(retried)
    return updated


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
