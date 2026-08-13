import math

from sqlalchemy import text

from app.db import session

# 1事例あたり約47媒体ある。そのまま出すと全リリースに自動転載される媒体で埋まるので絞る
PER_CASE = 4
OVERALL = 6

# この割合を超える事例に出ている媒体は, 何を書いても載る媒体とみなして落とす（実測の下駄・§8.3）
UBIQUITOUS_RATIO = 0.5

# 媒体ごとの出現事例数は media_frequency に, その分母は media_total に入れてある。
# 6百万行の corpus_media を毎クエリ GROUP BY し直さないための引き当て
DISTINCTIVE_SQL = text("""
    SELECT m.company_id, m.release_id, m.new_site_name,
           COALESCE(f.case_count, 1) AS document_frequency,
           (SELECT case_count FROM media_total LIMIT 1) AS total
    FROM corpus_media m
    JOIN unnest(CAST(:companies AS bigint[]), CAST(:releases AS bigint[])) AS t(company_id, release_id)
      ON m.company_id = t.company_id AND m.release_id = t.release_id
    LEFT JOIN media_frequency f ON f.new_site_name = m.new_site_name
""")


async def distinctive(pairs: list[tuple[int, int]]) -> tuple[dict[tuple[int, int], list[str]], list[str]]:
    """引いた事例を拾っていた媒体のうち, その事例群に特徴的なものを返す。

    Args:
        pairs: 事例の (company_id, release_id)。

    Returns:
        事例ごとの媒体名と, 事例群全体で特徴的な媒体名。
    """
    if not pairs:
        return {}, []

    params = {"companies": [c for c, _ in pairs], "releases": [r for _, r in pairs]}
    async with session() as db:
        rows = (await db.execute(DISTINCTIVE_SQL, params)).all()
    if not rows:
        return {}, []

    total = rows[0].total
    limit = len(pairs) * UBIQUITOUS_RATIO

    # 事例群での出現数 × 希少さ。全国メディアは希少さが効かず, 地方紙と地域経済新聞が上に来る
    hits: dict[str, int] = {}
    frequency: dict[str, int] = {}
    for r in rows:
        hits[r.new_site_name] = hits.get(r.new_site_name, 0) + 1
        frequency[r.new_site_name] = r.document_frequency
    scored = {
        name: count * math.log(total / max(frequency[name], 1))
        for name, count in hits.items()
        if count <= limit  # 引いた事例のほとんどに出ている媒体は, 内容と無関係に載る媒体
    }
    ranked = sorted(scored, key=lambda name: -scored[name])

    per_case: dict[tuple[int, int], list[str]] = {}
    order = {name: i for i, name in enumerate(ranked)}
    for r in rows:
        if r.new_site_name in order:
            per_case.setdefault((r.company_id, r.release_id), []).append(r.new_site_name)
    for key, names in per_case.items():
        per_case[key] = sorted(names, key=lambda n: order[n])[:PER_CASE]

    return per_case, ranked[:OVERALL]
