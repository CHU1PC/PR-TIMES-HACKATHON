from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import text

from app.db import session
from app.llm.embeddings import embed
from app.llm.openai_gpt import chatgpt
from app.llm.proposal.prompts import CATEGORY_PROMPT, NOTHING_UNDECIDED, SLOT_LABELS, SUGGESTION_PROMPT
from app.llm.proposal.schema import CategoryPick, SuggestionSet
from app.retrieval.index import search
from app.retrieval.media import distinctive
from app.retrieval.place import resolve_prefecture
from app.schema.proposal import ProposalResponse, Suggestion
from app.sparring.core import has_value
from app.sparring.slots import SLOT_ORDER

if TYPE_CHECKING:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import Runnable

    from app.schema import PlanDraft, SlotCode
    from app.schema.proposal import ProposalCase

CATEGORIES_SQL = text("SELECT business_category_name, business_category_id FROM categories")

PREFECTURE_SQL = text("SELECT name FROM places WHERE kind = 'prefecture' AND prefecture_id = :prefecture_id LIMIT 1")

# 事例をこの件数まで渡す。増やすほど LLM が薄い共通点を拾いに行くので絞る
TOP_K = 8

# 未定が多い予定はタイトルしか手掛かりが無く, 意味の近さだけでは的外れになる。
# 広めに取ってから業種と地域で拾い直す
FETCH_MULTIPLIER = 3

# 未定1件あたりの上乗せ。index.py の加点 0.04 に足す形で効き, 全部未定なら 0.12 増える
SPARSE_BONUS = 0.02

# 業種は数百件と小さいので初回に読み切って使い回す(async 関数には functools.cache が使えない)
_categories: dict[str, int] = {}

_category_chain: Runnable[dict[str, str], CategoryPick] = CATEGORY_PROMPT | chatgpt.with_structured_output(CategoryPick)


def build_suggestion_chain(prompt: ChatPromptTemplate) -> Runnable[dict[str, str], SuggestionSet]:
    """提案チェーンを組む。評価でプロンプトを差し替えられるように外に出してある。

    Args:
        prompt: 提案プロンプト。

    Returns:
        draft と undecided と cases を渡すと提案を返すチェーン。
    """
    return prompt | chatgpt.with_structured_output(SuggestionSet)


_suggestion_chain = build_suggestion_chain(SUGGESTION_PROMPT)


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


async def prefecture_name(prefecture_id: int | None) -> str | None:
    """都道府県IDを表記に戻す。クエリに「熊本県」を足すために引く。

    Args:
        prefecture_id: 都道府県ID。None なら引かない。

    Returns:
        都道府県名。引けなければ None。
    """
    if prefecture_id is None:
        return None
    async with session() as db:
        return (await db.execute(PREFECTURE_SQL, {"prefecture_id": prefecture_id})).scalar_one_or_none()


def undecided(draft: PlanDraft) -> list[SlotCode]:
    """まだ埋まっていない項目を並べる。聞いて該当が無かった skipped もここに入る。

    Args:
        draft: 壁打ちで埋めたイベント内容。

    Returns:
        SLOT_ORDER の順に並んだ未定の項目。
    """
    return [code for code in SLOT_ORDER if not has_value(draft, code)]


def format_undecided(codes: list[SlotCode]) -> str:
    """未定の項目をプロンプトに埋める形に整える。

    Args:
        codes: 未定の項目。

    Returns:
        1件1行の文字列。
    """
    return "\n".join(f"- {SLOT_LABELS[code]}" for code in codes) if codes else NOTHING_UNDECIDED


def query_text(draft: PlanDraft, business_category: str | None, prefecture: str | None) -> str:
    """検索に投げる文字列を組み立てる。未定で減った分を業種名と都道府県名で補う。

    Args:
        draft: 壁打ちで埋めたイベント内容。
        business_category: 推定した業種名。
        prefecture: place から解決した都道府県名。

    Returns:
        埋め込むクエリ。
    """
    parts = [draft.title, business_category, prefecture, draft.place, *draft.partner, draft.novelty, draft.observation]
    return " ".join(part for part in parts if part)


def match_bonus(case: ProposalCase, business_category: str | None, prefecture: str | None) -> int:
    """事例が顧客の業種・地域とどれだけ揃っているかを数える。

    Args:
        case: 検索で得た事例。
        business_category: 推定した業種名。
        prefecture: 解決した都道府県名。

    Returns:
        一致した数。0〜2。
    """
    category_hit = business_category is not None and case.business_category == business_category
    prefecture_hit = prefecture is not None and case.prefecture == prefecture
    return int(category_hit) + int(prefecture_hit)


def rerank(
    cases: list[ProposalCase],
    *,
    business_category: str | None,
    prefecture: str | None,
    bonus: float,
    top_k: int,
) -> list[ProposalCase]:
    """未定が多いときだけ, 同業種・同地域の事例を引き上げ直す。

    Args:
        cases: 検索で得た事例。
        business_category: 推定した業種名。
        prefecture: 解決した都道府県名。
        bonus: 一致1つあたりの上乗せ。0 なら並びは変わらない。
        top_k: 残す件数。

    Returns:
        並べ直した事例。
    """
    lifted = {
        (case.company_id, case.release_id): case.similarity + bonus * match_bonus(case, business_category, prefecture)
        for case in cases
    }
    return sorted(cases, key=lambda case: -lifted[case.company_id, case.release_id])[:top_k]


def format_cases(cases: list[ProposalCase]) -> str:
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


async def classify(draft: PlanDraft) -> tuple[str | None, int | None]:
    """予定をコーパスの業種に当てる。

    Args:
        draft: 壁打ちで埋めたイベント内容。

    Returns:
        業種名と業種ID。当てられなければ両方 None。
    """
    table = await categories()
    pick = await _category_chain.ainvoke({"draft": draft.model_dump_json(), "categories": "\n".join(table)})
    name = pick.business_category_name or ""
    return (name, table[name]) if name in table else (None, None)


async def propose(
    draft: PlanDraft,
    *,
    chain: Runnable[dict[str, str], SuggestionSet] | None = None,
) -> ProposalResponse:
    """壁打ちで聞き終えた予定に対し, 事例を引いて足せることを提案する。

    Args:
        draft: 壁打ちで埋めたイベント内容。未定の項目が残っていてよい。
        chain: 差し替える提案チェーン。評価でプロンプトを比べるときだけ渡す。

    Returns:
        提案3件と, 根拠にした事例。
    """
    open_slots = undecided(draft)
    picked, prefecture_id = await asyncio.gather(classify(draft), resolve_prefecture(draft.place))
    business_category, business_category_id = picked
    prefecture = await prefecture_name(prefecture_id)

    vector = await embed(query_text(draft, business_category, prefecture))
    fetched = await search(
        vector,
        business_category_id=business_category_id,
        prefecture_id=prefecture_id,
        top_k=TOP_K * FETCH_MULTIPLIER,
    )
    cases = rerank(
        fetched,
        business_category=business_category,
        prefecture=prefecture,
        bonus=SPARSE_BONUS * len(open_slots),
        top_k=TOP_K,
    )
    logger.info(
        "検索 業種={} 都道府県={} 未定={}件 事例={}件", business_category_id, prefecture_id, len(open_slots), len(cases)
    )

    if not cases:
        return ProposalResponse(suggestions=[], cases=[], media=[])

    per_case, overall = await distinctive([(c.company_id, c.release_id) for c in cases])
    for case in cases:
        case.media = per_case.get((case.company_id, case.release_id), [])

    result = await (chain or _suggestion_chain).ainvoke(
        {
            "draft": draft.model_dump_json(),
            "undecided": format_undecided(open_slots),
            "cases": format_cases(cases),
        }
    )
    # 未定を埋める提案を先に出す。3件しか見せないので並びが見え方を決める
    ordered = sorted(result.suggestions, key=lambda s: s.addresses not in open_slots)
    return ProposalResponse(
        suggestions=[
            Suggestion(
                action=s.action,
                reason=s.reason,
                cited=sorted({n - 1 for n in s.cited if 1 <= n <= len(cases)}),
            )
            for s in ordered
        ],
        cases=cases,
        media=overall,
    )
