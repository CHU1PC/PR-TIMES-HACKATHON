from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from scipy.stats import rankdata

from ml import features, metrics
from ml.baseline import knn_scores
from ml.dataset import RANDOM_SEED, Split, feature_matrix, load_corpus, make_split
from ml.embed_plans import ACCEPTANCE_PLANS, PLAN_VECTOR_PATH
from ml.paths import ARTIFACT_DIR, DEPLOY_MODEL_PATH, DEPLOY_SPLIT, SPLIT_NAMES
from ml.predict import PlanScorer

# 業種も県も指定しないときの番兵。コーパス側は 0〜92 なので絶対に一致しない
NO_CATEGORY = -1

RESULT_PATH = ARTIFACT_DIR / "results.json"
MEGABYTE = 1024 * 1024


def baseline_predictions(corpus: pd.DataFrame, vectors: np.ndarray, split: Split) -> np.ndarray:
    """近傍プールを train 行だけに絞って k-NN ベースラインを走らせる。

    Args:
        corpus: load_corpus() の DataFrame。
        vectors: 同じ行順の埋め込み。
        split: 行マスク。

    Returns:
        test 行と同じ並びのベースラインスコア。
    """
    category = corpus["business_category_id"].fillna(features.MISSING_CATEGORY).to_numpy()
    prefecture = corpus["prefecture_id"].fillna(features.MISSING_CATEGORY).to_numpy()
    return knn_scores(
        vectors[split.test],
        category[split.test],
        prefecture[split.test],
        vectors[split.train],
        category[split.train],
        prefecture[split.train],
        corpus["pv_score"].to_numpy()[split.train],
    )


def model_predictions(corpus: pd.DataFrame, vectors: np.ndarray, split: Split) -> dict[str, np.ndarray]:
    """保存済みの4モデルと, LightGBM + MLP の順位平均を test 行に当てる。

    Args:
        corpus: load_corpus() の DataFrame。
        vectors: 同じ行順の埋め込み。
        split: 行マスク。

    Returns:
        モデル名から test 行の予測への辞書。
    """
    directory = ARTIFACT_DIR / split.name
    matrix = feature_matrix(corpus, vectors)[split.test]
    encoder = joblib.load(directory / "encoder.joblib")
    dense = encoder.transform(matrix)

    predictions = {
        "lgbm": PlanScorer.load(directory / "lgbm.txt").booster.predict(matrix),
        # RandomForest は LightGBM と同じ 259列。one-hot ではなく生のカテゴリIDを渡して条件を揃える
        "forest": joblib.load(directory / "forest.joblib").predict(matrix),
        "ridge": joblib.load(directory / "ridge.joblib").predict(dense),
        "mlp": joblib.load(directory / "mlp.joblib").predict(dense),
    }
    # 値域が違うモデルを混ぜるので, 平均ではなく順位で足す。pv_score と同じ 0〜1 に戻して RMSE も測れるようにする
    rows = len(matrix)
    predictions["lgbm+mlp"] = (rankdata(predictions["lgbm"]) + rankdata(predictions["mlp"])) / (2 * rows)
    return predictions


def evaluate_split(name: str, corpus: pd.DataFrame, vectors: np.ndarray) -> dict[str, dict[str, float]]:
    """1つの分割でベースラインと各モデルを同じ hold-out で測る。

    Args:
        name: 分割名。
        corpus: load_corpus() の DataFrame。
        vectors: 同じ行順の埋め込み。

    Returns:
        モデル名から指標への辞書。
    """
    split = make_split(name, corpus, RANDOM_SEED)
    actual = corpus["pv_score"].to_numpy()[split.test]
    company_id = corpus["company_id"].to_numpy()[split.test]
    print(f"\n=== {name} {split.sizes()} ===")

    scored = {"knn_baseline": baseline_predictions(corpus, vectors, split)}
    scored.update(model_predictions(corpus, vectors, split))

    table = {model: metrics.report(prediction, actual, company_id) for model, prediction in scored.items()}
    print(pd.DataFrame(table).T.to_string(float_format=lambda v: f"{v:.4f}"))

    for model in ("lgbm", "forest"):
        low, high = metrics.bootstrap_gap(scored[model], scored["knn_baseline"], actual)
        print(f"{model} - knn_baseline の Spearman 差 95%区間 [{low:+.4f}, {high:+.4f}]")
        table[model]["gap_vs_baseline_low"] = low
        table[model]["gap_vs_baseline_high"] = high
    return table


def acceptance_table(corpus: pd.DataFrame, vectors: np.ndarray) -> pd.DataFrame:
    """受け入れテストの予定文をベースラインと学習モデルの両方で採点する。

    Args:
        corpus: load_corpus() の DataFrame。
        vectors: 同じ行順の埋め込み。

    Returns:
        予定文ごとのスコアと順位の表。
    """
    plans = np.load(PLAN_VECTOR_PATH)
    titles = list(ACCEPTANCE_PLANS)
    absent = np.full(len(titles), NO_CATEGORY)

    baseline = knn_scores(
        plans,
        absent,
        absent,
        vectors,
        corpus["business_category_id"].fillna(features.MISSING_CATEGORY).to_numpy(),
        corpus["prefecture_id"].fillna(features.MISSING_CATEGORY).to_numpy(),
        corpus["pv_score"].to_numpy(),
    )
    model = PlanScorer.load(DEPLOY_MODEL_PATH).score_many(plans, titles)

    table = pd.DataFrame({"plan": titles, "knn_baseline": baseline, "lgbm": model})
    table["knn_rank"] = table["knn_baseline"].rank(ascending=False).astype(int)
    table["lgbm_rank"] = table["lgbm"].rank(ascending=False).astype(int)
    print("\n=== 受け入れテスト(業種・都道府県は指定しない) ===")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    return table


def artifact_sizes() -> dict[str, float]:
    """本番に載せるファイルの大きさを MB で出す。

    Returns:
        ファイル名から MB への辞書。
    """
    directory = ARTIFACT_DIR / DEPLOY_SPLIT
    sizes = {p.name: p.stat().st_size / MEGABYTE for p in sorted(directory.iterdir()) if p.is_file()}
    print("\n=== 成果物 ===")
    for name, size in sizes.items():
        print(f"{name:16s} {size:8.2f} MB")
    return sizes


def main() -> None:
    """全分割の指標と受け入れテストを出して results.json に残す。"""
    corpus, vectors = load_corpus()
    results = {name: evaluate_split(name, corpus, vectors) for name in SPLIT_NAMES}
    acceptance = acceptance_table(corpus, vectors)
    sizes = artifact_sizes()

    payload = {"splits": results, "acceptance": acceptance.to_dict(orient="records"), "artifact_mb": sizes}
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n書き出し {RESULT_PATH}")


if __name__ == "__main__":
    main()
