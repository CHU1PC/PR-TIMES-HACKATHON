"""アドバイスの前後で plan_score がどれだけ動くかを, プロンプトの新旧で比べる。

`DATABASE_URL=... uv run --group etl --env-file ../.env python -m eval.lift --n 30` で回す。
corpus.parquet を読むので duckdb (etl グループ) が要る。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING

import duckdb
import numpy as np
from langchain_core.runnables import RunnableLambda
from loguru import logger

from app.llm.embeddings import embed
from app.llm.proposal.prompts import SUGGESTION_PROMPT
from app.proposal.core import build_suggestion_chain, propose, undecided
from app.ranking import plan_score
from app.schema import PlanDraft
from app.settings import DATA_DIR
from eval.legacy_prompt import LEGACY_SUGGESTION_PROMPT

if TYPE_CHECKING:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import Runnable

    from app.llm.proposal.schema import SuggestionSet
    from app.schema import SlotCode
    from app.schema.proposal import ProposalResponse, Suggestion

CORPUS = DATA_DIR / "corpus.parquet"

# 1語しかないタイトルは予定として復元しても意味を持たない
MIN_TITLE_LENGTH = 12

SAMPLE_SQL = """
    SELECT title, business_category_id, prefecture_id, prefecture_name, city_name
    FROM read_parquet($path)
    WHERE title IS NOT NULL AND length(title) >= $min_title
"""

ALL_SLOTS: tuple[SlotCode, ...] = ("place", "partner", "people", "novelty", "observation", "video")

# 対応比較を出すのは arm がちょうど2本のときだけ
PAIR = 2

# 会社名の照合から落とす法人格。「株式会社GF」を「GF」で見る
CORPORATE_FORMS = ("株式会社", "有限会社", "合同会社", "合資会社", "一般社団法人", "特定非営利活動法人", "学校法人")

# 1文字の社名は普通の語に当たってしまう
MIN_NAME_LENGTH = 2

# 事例に由来しない, 提案3件と同じくらいの長さの当たり障りない文。
# 「文字を足すだけでスコアが動くのか」を切り分ける対照
FILLER = (
    "当日の流れをあらためて確認する 手元の資料を一度そろえておく "
    "関係する人に日程を伝えておく 終わったあとに気づいたことを書き留めておく"
)

LIMITS = """
この指標の限界:
- 測っているのは埋め込み空間での移動であって, 実際に反響が増えることの証明ではない
- plan_score は「近い事例が実際どれだけ読まれたか」の中央値。予定そのものの実測値ではない
- 予定はコーパスの実配信タイトルから復元している。before の近傍にはその行自身が入りうる(自己一致で before が高めに出る)
- 提案文を足せば文字数が増える。その分だけの動きは filler 行(事例に由来しない当たり障りない文)と比べて読む
- 新旧どちらの arm も同じ SuggestionSet(addresses 付き)で構造化している。旧プロンプト側にも枠だけは渡っている
- 「未定の被覆」は LLM の自己申告(addresses)を数えたもの。本文が本当にその項目を埋めているかは別に読む
- 「他社名混入」は事例の company_name の文字列一致。言い換えられた名前や商品名は取りこぼす(下限値)
- **プロンプトの相対比較にしか使えない。**絶対値を成果として読まない
"""


@dataclass(frozen=True)
class Sample:
    """コーパス1行から復元した評価用の予定。"""

    draft: PlanDraft
    business_category_id: int | None
    prefecture_id: int | None


@dataclass(frozen=True)
class Arm:
    """1つのプロンプトで1件を通した結果。"""

    after: float
    suggestions: int
    covered: int
    leaks: int


@dataclass(frozen=True)
class Result:
    """1件の予定の前後差。before は arm 間で共有する。"""

    title: str
    before: float
    filler: float
    arms: dict[str, Arm]


def load_rows() -> list[tuple[str, int | None, int | None, str | None, str | None]]:
    """コーパスから復元元になる行を読む。

    Returns:
        (タイトル, 業種ID, 都道府県ID, 都道府県名, 市区町村名) の一覧。
    """
    with duckdb.connect() as con:
        return con.execute(SAMPLE_SQL, {"path": str(CORPUS), "min_title": MIN_TITLE_LENGTH}).fetchall()


def build_sample(
    row: tuple[str, int | None, int | None, str | None, str | None],
    *,
    keep_place: bool,
) -> Sample:
    """1行を PlanDraft に復元する。復元できない項目は skipped に入れる。

    Args:
        row: load_rows の1行。
        keep_place: 場所を埋めたまま渡すか。False なら場所も未定にする。

    Returns:
        評価用の予定。
    """
    title, business_category_id, prefecture_id, prefecture, city = row
    place = (city or prefecture) if keep_place else None
    skipped = [code for code in ALL_SLOTS if code != "place" or place is None]
    return Sample(
        draft=PlanDraft(title=title, place=place, skipped=skipped),
        business_category_id=business_category_id,
        prefecture_id=prefecture_id,
    )


def plan_text(draft: PlanDraft) -> str:
    """採点にかける予定の文字列。core.query_text とは別に固定し, 比較を core の変更から切り離す。

    Args:
        draft: 評価用の予定。

    Returns:
        埋め込む文字列。
    """
    parts = [draft.title, draft.place, *draft.partner, draft.novelty, draft.observation]
    return " ".join(part for part in parts if part)


def advised_text(draft: PlanDraft, suggestions: list[Suggestion]) -> str:
    """提案を足した後の予定の文字列。根拠文は事例の引き写しになるので action だけ足す。

    Args:
        draft: 評価用の予定。
        suggestions: 提案。

    Returns:
        埋め込む文字列。
    """
    return " ".join([plan_text(draft), *(s.action for s in suggestions)])


def bare_name(name: str) -> str:
    """会社名から法人格を落とす。「株式会社RESPIRER」を「RESPIRER」で照合するため。

    Args:
        name: コーパスの会社名。

    Returns:
        法人格を除いた表記。
    """
    for form in CORPORATE_FORMS:
        name = name.replace(form, "")
    return name.strip()


def leaks(response: ProposalResponse) -> int:
    """事例側の会社名が混ざった提案の件数を数える。

    Args:
        response: 提案と, 根拠にした事例。

    Returns:
        会社名が1つでも入っていた提案の件数。
    """
    names = {bare_name(c.company_name) for c in response.cases if c.company_name}
    hits = {n for n in names if len(n) >= MIN_NAME_LENGTH}
    return sum(1 for s in response.suggestions if any(n in f"{s.action} {s.reason}" for n in hits))


def recorder(store: list[SuggestionSet]) -> Runnable[SuggestionSet, SuggestionSet]:
    """通り抜けた提案を控えるだけの段。addresses は API 応答に載らないのでここで拾う。

    Args:
        store: 控えの置き場。

    Returns:
        素通しの Runnable。
    """

    def keep(result: SuggestionSet) -> SuggestionSet:
        """控えて素通しする。

        Args:
            result: LLM が返した提案。

        Returns:
            受け取ったものをそのまま。
        """
        store.append(result)
        return result

    return RunnableLambda(keep)


async def score(text: str, sample: Sample) -> float | None:
    """文字列を採点する。業種と地域はコーパスの実値を使い, arm 間で揃える。

    Args:
        text: 採点する文字列。
        sample: 評価用の予定。

    Returns:
        0〜1 のスコア。近傍が引けなければ None。
    """
    vector = await embed(text)
    return await plan_score(
        vector,
        business_category_id=sample.business_category_id,
        prefecture_id=sample.prefecture_id,
    )


async def run_arm(sample: Sample, prompt: ChatPromptTemplate) -> Arm | None:
    """1つのプロンプトで提案を作り, 提案後のスコアを出す。

    Args:
        sample: 評価用の予定。
        prompt: 提案プロンプト。

    Returns:
        提案後のスコアと提案の内訳。採点できなければ None。
    """
    store: list[SuggestionSet] = []
    response = await propose(sample.draft, chain=build_suggestion_chain(prompt) | recorder(store))
    if not response.suggestions:
        return None
    after = await score(advised_text(sample.draft, response.suggestions), sample)
    if after is None:
        return None
    open_slots = set(undecided(sample.draft))
    # 同じ項目を3件で言い換えても被覆1。散らせたかを見る
    covered = len({s.addresses for s in store[0].suggestions if s.addresses in open_slots}) if store else 0
    return Arm(after=after, suggestions=len(response.suggestions), covered=covered, leaks=leaks(response))


async def evaluate(
    sample: Sample,
    prompts: dict[str, ChatPromptTemplate],
    gate: asyncio.Semaphore,
) -> Result | None:
    """1件を before と全 arm ぶん通す。

    Args:
        sample: 評価用の予定。
        prompts: arm 名 → プロンプト。
        gate: 同時実行数の上限。

    Returns:
        1件ぶんの結果。どこかで採点できなければ None。
    """
    async with gate:
        before = await score(plan_text(sample.draft), sample)
        filler = await score(f"{plan_text(sample.draft)} {FILLER}", sample)
        if before is None or filler is None:
            return None
        arms: dict[str, Arm] = {}
        for name, prompt in prompts.items():
            arm = await run_arm(sample, prompt)
            if arm is None:
                return None
            arms[name] = arm
        return Result(title=sample.draft.title, before=before, filler=filler, arms=arms)


def win_rate(values: list[float]) -> float:
    """0 を超えた割合を返す。

    Args:
        values: 差分の一覧。

    Returns:
        0〜1 の割合。空なら 0。
    """
    return sum(1 for v in values if v > 0) / len(values) if values else 0.0


def report(results: list[Result], names: list[str]) -> str:
    """集計結果を1つの文字列にまとめる。

    Args:
        results: 全件の結果。
        names: arm 名。

    Returns:
        表示する本文。
    """
    lines = ["arm    n   before中央値  after中央値   lift中央値   勝率     提案/件  未定の被覆/件  他社名混入"]
    lifts: dict[str, list[float]] = {}
    for name in names:
        lift = [r.arms[name].after - r.before for r in results]
        lifts[name] = lift
        made = sum(r.arms[name].suggestions for r in results)
        covered = sum(r.arms[name].covered for r in results) / len(results)
        leaked = sum(r.arms[name].leaks for r in results)
        lines.append(
            f"{name:<6} {len(results):<3} {median(r.before for r in results):<13.4f} "
            f"{median(r.arms[name].after for r in results):<13.4f} {median(lift):<+12.4f} "
            f"{win_rate(lift):<8.1%} {made / len(results):<8.2f} {covered:<13.2f} {leaked}/{made}"
        )

    dilution = [r.filler - r.before for r in results]
    lines.append(
        f"{'filler':<6} {len(results):<3} {median(r.before for r in results):<13.4f} "
        f"{median(r.filler for r in results):<13.4f} {median(dilution):<+12.4f} "
        f"{win_rate(dilution):<8.1%} {'-':<8} {'-':<13} -"
    )

    if len(names) == PAIR:
        head, tail = names
        paired = [a - b for a, b in zip(lifts[head], lifts[tail], strict=True)]
        lines.extend(
            [
                "",
                f"対応比較 (同じ予定・同じ before): {head} - {tail}",
                f"  lift 差の中央値 = {median(paired):+.4f} / {head} が勝った割合 = {win_rate(paired):.1%}",
            ]
        )
    return "\n".join(lines)


async def main() -> None:
    """コーパスからサンプルして新旧プロンプトの lift を比べる。"""
    parser = argparse.ArgumentParser(description="アドバイス前後の plan_score の動きを新旧プロンプトで比べる")
    parser.add_argument("--n", type=int, default=30, help="サンプル数。API を叩くので控えめに")
    parser.add_argument("--seed", type=int, default=42, help="サンプルの乱数種")
    parser.add_argument("--keep-place", action="store_true", help="場所だけ埋めたまま渡す。既定は全項目を未定にする")
    parser.add_argument("--concurrency", type=int, default=4, help="同時に走らせる件数")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stdout, format="{message}", level="WARNING")

    rows = load_rows()
    picked = np.random.default_rng(args.seed).choice(len(rows), size=args.n, replace=False)
    samples = [build_sample(rows[int(i)], keep_place=args.keep_place) for i in picked]

    prompts: dict[str, ChatPromptTemplate] = {"new": SUGGESTION_PROMPT, "old": LEGACY_SUGGESTION_PROMPT}
    gate = asyncio.Semaphore(args.concurrency)
    # 1件の失敗で全件を捨てない。落ちた分は成立 n から外れる
    done = await asyncio.gather(*(evaluate(s, prompts, gate) for s in samples), return_exceptions=True)
    for outcome in done:
        if isinstance(outcome, BaseException):
            logger.warning("失敗 {}", type(outcome).__name__)
    results = [r for r in done if isinstance(r, Result)]
    if not results:
        logger.error("1件も採点できなかった")
        return

    scenario = "場所のみ既知" if args.keep_place else "全項目が未定"
    header = (
        f"=== 提案前後の plan_score ===\n"
        f"{CORPUS.name} / 要求 n={args.n} / 成立 n={len(results)} / seed={args.seed} / {scenario}"
    )
    logger.warning("\n".join([header, "", report(results, list(prompts)), LIMITS]))


if __name__ == "__main__":
    asyncio.run(main())
