from langchain_core.runnables import Runnable

from app.llm.hearing.prompts import PROMPT
from app.llm.hearing.schema import HearingStep
from app.llm.openai_gpt import chatgpt
from app.schema import Candidate, Exchange, HearingResponse

_chain: Runnable[dict[str, str], HearingStep] = PROMPT | chatgpt.with_structured_output(HearingStep)

# LLM の done 判断が甘くても終わるようにする上限。相手は広報の専任がいない忙しい担当者
MAX_EXCHANGES = 6


async def step(history: list[Exchange], answer: str) -> HearingResponse:
    """聞き取りを1往復進める。

    Args:
        history: ここまでの往復。
        answer: 直前の質問への返答。初回は空。

    Returns:
        更新後の履歴と, 次に聞くこと。
    """
    updated = list(history)
    if answer.strip() and updated:
        updated[-1] = Exchange(question=updated[-1].question, answer=answer.strip())

    formatted = "\n\n".join(f"Q: {e.question}\nA: {e.answer}" for e in updated) or "(まだ何も聞いていません)"
    result = await _chain.ainvoke({"history": formatted})
    candidates = [
        Candidate(title=p.title, category=p.category, source=p.source, reason=p.reason) for p in result.candidates
    ]

    done = result.done or len(updated) >= MAX_EXCHANGES or result.question is None
    if not done:
        updated.append(Exchange(question=result.question or "", answer=""))

    return HearingResponse(
        history=updated,
        question=None if done else result.question,
        hint=None if done else result.hint,
        candidates=candidates,
        done=done,
    )
