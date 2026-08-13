import duckdb
from loguru import logger

from app.settings import DATA_DIR

DB = DATA_DIR / "analysis.duckdb"

# 選抜結果そのもの。enrich が本文を合流させる元になるので, 一度作ったら上書きしない限り不変
OUT = DATA_DIR / "corpus_base.parquet"

# 埋め込みと検索が読む唯一のファイル。本文抽出前は base の写しで, 抽出後は enrich が作り直す
CORPUS = DATA_DIR / "corpus.parquet"

PLACES = DATA_DIR / "places.parquet"
CATEGORIES = DATA_DIR / "categories.parquet"

# 2023年以降に絞る。媒体の顔ぶれは年々入れ替わるので, 古い事例を根拠にすると現在の届き方とずれる
SINCE = "2023-01-01"

# 層 = 業種 × リリース種別 × 都道府県。各層から reach 上位をこの件数だけ取る。
# 全国メディアが強い業種だけでコーパスが埋まるのを防ぐため, 層ごとに同数を割り当てる
PER_STRATUM = 25

# release_location は1リリースに複数行入る（実測 236,017 件）。市区町村がある行を優先して1行に畳む
PRIMARY_LOCATION = """
    SELECT company_id, release_id, prefecture_id, city_id
    FROM release_location
    QUALIFY row_number() OVER (
        PARTITION BY company_id, release_id
        ORDER BY (city_id IS NULL), prefecture_id, city_id
    ) = 1
"""

PRIMARY_CATEGORY = """
    SELECT company_id, release_id, business_category_id
    FROM release_category
    QUALIFY row_number() OVER (PARTITION BY company_id, release_id ORDER BY business_category_id) = 1
"""

# reach は PR TIMES 自身を除いたユニーク媒体数（wc_uniq_ex）。requirements §8.3 の目的変数
SELECT_CORPUS = f"""
WITH loc AS ({PRIMARY_LOCATION}),
     cat AS ({PRIMARY_CATEGORY}),
     cand AS (
        SELECT r.company_id, r.release_id, r.created_at, r.title,
               w.wc_uniq_ex AS reach,
               cat.business_category_id AS business_category_id,
               r.release_type_id AS release_type_id,
               loc.prefecture_id AS prefecture_id,
               loc.city_id AS city_id
        FROM release r
        JOIN wc_agg w USING (company_id, release_id)
        LEFT JOIN cat USING (company_id, release_id)
        LEFT JOIN loc USING (company_id, release_id)
        WHERE r.created_at >= '{{since}}'
          AND w.wc_uniq_ex > 0
          AND r.title IS NOT NULL
          AND r.title <> ''
     ),
     picked AS (
        SELECT * FROM cand
        -- company_id まで並べないと, 同一層で reach と release_id が同値のとき選抜が入れ替わる。
        -- 選抜がぶれると埋め込み(行番号で対応)がメタデータとずれるので, 完全に決定的にする
        QUALIFY row_number() OVER (
            PARTITION BY business_category_id, release_type_id, prefecture_id
            ORDER BY reach DESC, company_id, release_id
        ) <= {{per_stratum}}
     )
SELECT p.company_id, p.release_id, p.created_at, p.title, p.reach,
       p.business_category_id, bc.business_category_name,
       p.release_type_id, rt.release_type_name,
       p.prefecture_id, pf.prefecture_name,
       p.city_id, ci.city_name,
       co.company_name
FROM picked p
LEFT JOIN business_category bc USING (business_category_id)
LEFT JOIN release_type rt USING (release_type_id)
LEFT JOIN prefecture pf USING (prefecture_id)
LEFT JOIN city ci USING (city_id)
LEFT JOIN company co USING (company_id)
ORDER BY p.company_id, p.release_id
"""


def build(con: duckdb.DuckDBPyConnection) -> int:
    """層別に reach 上位を取り出して parquet に書き出す。

    Args:
        con: analysis.duckdb への読み取り接続。

    Returns:
        書き出した件数。
    """
    sql = SELECT_CORPUS.format(since=SINCE, per_stratum=PER_STRATUM)
    con.execute(f"COPY ({sql}) TO '{OUT}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    # 本文抽出はまだなので, この時点では base をそのまま検索対象にする
    if not CORPUS.exists():
        con.execute(f"COPY (SELECT * FROM read_parquet('{OUT}')) TO '{CORPUS}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return con.execute(f"SELECT count(*) FROM read_parquet('{OUT}')").fetchone()[0]


def report(con: duckdb.DuckDBPyConnection) -> None:
    """コーパスの偏りを確認できる要約を出す。

    Args:
        con: analysis.duckdb への読み取り接続。
    """
    stats = con.execute(f"""
        SELECT count(*), count(DISTINCT company_id), median(reach), min(reach), max(reach),
               count(*) FILTER (WHERE prefecture_id IS NOT NULL)
        FROM read_parquet('{OUT}')
    """).fetchone()
    logger.info(
        "件数 {:,} / 企業 {:,}社 / reach 中央値 {:.0f} (min {} max {}) / 地域あり {:,}",
        *stats[:5],
        stats[5],
    )


def build_lookups(con: duckdb.DuckDBPyConnection) -> None:
    """アプリが参照する地名と業種の索引を書き出す。DuckDB 本体(432MB)を配らずに済ませる。

    Args:
        con: analysis.duckdb への読み取り接続。
    """
    con.execute(f"""
        COPY (
            SELECT 'prefecture' AS kind, prefecture_name AS name, prefecture_id FROM prefecture
            UNION ALL
            SELECT 'city', city_name, prefecture_id FROM city
        ) TO '{PLACES}' (FORMAT PARQUET)
    """)
    # コーパスに事例が無い業種を分類先に出しても検索が空振りするので, 出現するものだけ渡す
    con.execute(f"""
        COPY (
            SELECT business_category_id, business_category_name, count(*) AS cases
            FROM read_parquet('{OUT}')
            WHERE business_category_id IS NOT NULL
            GROUP BY 1, 2
            ORDER BY 1
        ) TO '{CATEGORIES}' (FORMAT PARQUET)
    """)


def main() -> None:
    """analysis.duckdb から事例コーパスと索引を作る。"""
    with duckdb.connect(str(DB), read_only=True) as con:
        rows = build(con)
        logger.info("出力 {} ({:,}件 / {:.0f}MB)", OUT, rows, OUT.stat().st_size / 1024 / 1024)
        report(con)
        build_lookups(con)
        logger.info("索引 {} / {}", PLACES.name, CATEGORIES.name)


if __name__ == "__main__":
    main()
