import asyncio

from langchain_core.runnables import Runnable
from loguru import logger
from sqlalchemy import text

from app.db import session
from app.llm.embeddings import embed
from app.llm.openai_gpt import chatgpt
from app.llm.proposal.prompts import CATEGORY_PROMPT, SUGGESTION_PROMPT
from app.llm.proposal.schema import CategoryPick, SuggestionSet
from app.retrieval.index import search
from app.retrieval.media import distinctive
from app.retrieval.place import resolve_prefecture
from app.schema import PlanDraft
from app.schema.proposal import Case, ProposalResponse, Suggestion

CATEGORIES_SQL = text("SELECT business_category_name, business_category_id FROM categories")

# 事例をこの件数まで渡す。増やすほど LLM が薄い共通点を拾いに行くので絞る
TOP_K = 8

# 業種は数百件と小さいので初回に読み切って使い回す（async 関数には functools.cache が使えない）
_categories: dict[str, int] = {}

_category_chain: Runnable[dict[str, str], CategoryPick] = CATEGORY_PROMPT | chatgpt.with_structured_output(CategoryPick)
_suggestion_chain: Runnable[dict[str, str], SuggestionSet] = SUGGESTION_PROMPT | chatgpt.with_structured_output(
    SuggestionSet
)


async def categories() -> dict[str, int]:
    """コーパスに事例がある業種だけを1度だけ読み込む。

    Returns:
        業種名 → 業種ID。
    """
    if not _categories:
        async with session() as db:
            rows = (await db.execute(CATEGORIES_SQL)).tuples().all()
        _categories.update(rows)
    return _categories


def query_text(draft: PlanDraft) -> str:
    """予定を検索クエリの文字列にする。コーパス側は title を埋め込んでいるので語をそのまま並べる。

    Args:
        draft: 壁打ちで埋めたイベント内容。

    Returns:
        埋め込みに渡す文字列。
    """
    parts = [draft.title, draft.place, *draft.partner, draft.novelty, draft.observation]
    return " ".join(p for p in parts if p)


def format_cases(cases: list[Case]) -> str:
    """事例をプロンプトに埋める形に整える。**転載件数は渡さない。**

    Args:
        cases: 検索で得た事例。

    Returns:
        1件1ブロックの文字列。
    """
    blocks = []
    for number, c in enumerate(cases, 1):
        head = (
            f"#{number} "
            f"[{c.business_category or '業種不明'}/{c.release_type or '種別不明'}"
            f"/{(c.prefecture or '') + (c.city or '') or '地域なし'}]"
        )
        body = "\n  ".join(filter(None, [c.title, c.subtitle, c.body_head]))
        media = f"\n  拾った媒体: {', '.join(c.media)}" if c.media else ""
        blocks.append(f"{head}\n  {body}{media}")
    return "\n\n".join(blocks)


async def classify(draft: PlanDraft) -> int | None:
    """予定をコーパスの業種に当てる。

    Args:
        draft: 壁打ちで埋めたイベント内容。

    Returns:
        業種ID。当てられなければ None。
    """
    table = await categories()
    pick = await _category_chain.ainvoke({"draft": draft.model_dump_json(), "categories": "\n".join(table)})
    return table.get(pick.business_category_name or "")


async def propose(draft: PlanDraft) -> ProposalResponse:
    """壁打ちで固まった予定に対し, 事例を引いて足せることを提案する。

    Args:
        draft: 壁打ちで埋めたイベント内容。

    Returns:
        提案3件と, 根拠にした事例。
    """
    prefecture_id = await resolve_prefecture(draft.place)
    business_category_id, vector = await asyncio.gather(classify(draft), embed(query_text(draft)))
    cases = await search(vector, business_category_id=business_category_id, prefecture_id=prefecture_id, top_k=TOP_K)
    logger.info("検索 業種={} 都道府県={} 事例={}件", business_category_id, prefecture_id, len(cases))

    if not cases:
        return ProposalResponse(suggestions=[], cases=[], media=[])

    # 媒体名は LLM に作らせず, 転載ログから引く。作文されると実測でない媒体名が顧客に出る
    per_case, overall = await distinctive([(c.company_id, c.release_id) for c in cases])
    for case in cases:
        case.media = per_case.get((case.company_id, case.release_id), [])

    result = await _suggestion_chain.ainvoke({"draft": draft.model_dump_json(), "cases": format_cases(cases)})
    return ProposalResponse(
        suggestions=[
            Suggestion(
                action=s.action,
                reason=s.reason,
                # LLM は渡していない番号を書くことがある。範囲外は落とし, 1始まりを配列の位置に直す
                cited=sorted({n - 1 for n in s.cited if 1 <= n <= len(cases)}),
            )
            for s in result.suggestions
        ],
        cases=cases,
        media=overall,
    )
