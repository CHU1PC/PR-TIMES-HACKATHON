from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import joblib
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor

from ml import features
from ml.dataset import RANDOM_SEED, Split, feature_matrix, load_corpus, make_split
from ml.metrics import rmse, spearman
from ml.paths import ARTIFACT_DIR, DEPLOY_SPLIT, SPLIT_NAMES

if TYPE_CHECKING:
    import numpy as np

LGBM_PARAMS = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.03,
    "num_leaves": 63,
    "min_data_in_leaf": 50,
    # 256次元の埋め込みは1本1本が弱い。列を絞るほど valid が伸びた(0.5 → 0.2 で +0.010)
    "feature_fraction": 0.2,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbose": -1,
    "seed": RANDOM_SEED,
}
LGBM_ROUNDS = 4000
LGBM_PATIENCE = 100

RIDGE_ALPHAS = (0.1, 1.0, 10.0, 100.0)

MLP_HIDDEN = (256, 64)
MLP_EPOCHS = 60
MLP_PATIENCE = 8

FOREST_TREES = 200
# 既定の max_features=1.0 は 259列を毎回全部見るので桁違いに遅い。0.2 で LightGBM の feature_fraction と揃える
FOREST_MAX_FEATURES = 0.2
# 葉を1件まで伸ばすと木が肥大して 1本 3MB を超える。20件で止める
FOREST_MIN_LEAF = 20


def train_lgbm(matrix: np.ndarray, target: np.ndarray, split: Split) -> lgb.Booster:
    """LightGBM を valid で早期終了させながら学習する。

    Args:
        matrix: 全行の特徴行列。
        target: 全行の pv_score。
        split: 行マスク。

    Returns:
        学習済みの Booster。
    """
    names = features.FEATURE_NAMES
    categorical = list(features.CATEGORY_FEATURES)
    train_set = lgb.Dataset(
        matrix[split.train], target[split.train], feature_name=names, categorical_feature=categorical
    )
    valid_set = lgb.Dataset(matrix[split.valid], target[split.valid], reference=train_set)
    return lgb.train(
        LGBM_PARAMS,
        train_set,
        num_boost_round=LGBM_ROUNDS,
        valid_sets=[valid_set],
        callbacks=[lgb.early_stopping(LGBM_PATIENCE, verbose=False)],
    )


def train_forest(matrix: np.ndarray, target: np.ndarray, split: Split) -> RandomForestRegressor:
    """LightGBM と同じ 259列で RandomForest を学習する。早期終了は無いので valid は使わない。

    Args:
        matrix: 全行の特徴行列。
        target: 全行の pv_score。
        split: 行マスク。

    Returns:
        学習済みの RandomForestRegressor。

    Note:
        カテゴリ2本は native categorical が無いので順序値として扱われる。
    """
    model = RandomForestRegressor(
        n_estimators=FOREST_TREES,
        max_features=FOREST_MAX_FEATURES,
        min_samples_leaf=FOREST_MIN_LEAF,
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )
    return model.fit(matrix[split.train], target[split.train])


def train_ridge(dense: np.ndarray, target: np.ndarray, split: Split) -> tuple[Ridge, float]:
    """Ridge の alpha を valid の RMSE で選ぶ。

    Args:
        dense: one-hot 展開済みの特徴行列。
        target: 全行の pv_score。
        split: 行マスク。

    Returns:
        学習済みモデルと, 選んだ alpha。
    """
    best_model = Ridge(alpha=RIDGE_ALPHAS[0])
    best_alpha = RIDGE_ALPHAS[0]
    best_error = float("inf")
    for alpha in RIDGE_ALPHAS:
        model = Ridge(alpha=alpha).fit(dense[split.train], target[split.train])
        error = rmse(model.predict(dense[split.valid]), target[split.valid])
        if error < best_error:
            best_model, best_alpha, best_error = model, alpha, error
    return best_model, best_alpha


def train_mlp(dense: np.ndarray, target: np.ndarray, split: Split) -> tuple[MLPRegressor, int]:
    """企業単位の valid で早期終了させて MLP を学習する。

    Args:
        dense: one-hot 展開済みの特徴行列。
        target: 全行の pv_score。
        split: 行マスク。

    Returns:
        最良エポックの重みに戻したモデルと, そのエポック数。
    """
    model = MLPRegressor(
        hidden_layer_sizes=MLP_HIDDEN,
        alpha=1e-3,
        learning_rate_init=1e-3,
        batch_size=512,
        random_state=RANDOM_SEED,
    )
    best_error = float("inf")
    best_epoch = 0
    best_weights: tuple[list[np.ndarray], list[np.ndarray]] = ([], [])

    for epoch in range(1, MLP_EPOCHS + 1):
        # sklearn 内蔵の early_stopping は train を行単位で切るので, 同じ企業が両側に残る
        model.partial_fit(dense[split.train], target[split.train])
        error = rmse(model.predict(dense[split.valid]), target[split.valid])
        if error < best_error:
            best_error, best_epoch = error, epoch
            best_weights = ([c.copy() for c in model.coefs_], [b.copy() for b in model.intercepts_])
        elif epoch - best_epoch >= MLP_PATIENCE:
            break

    model.coefs_, model.intercepts_ = best_weights
    return model, best_epoch


@dataclass(frozen=True)
class Trained:
    """1つの分割で学習した4モデルと, その学習秒数。"""

    booster: lgb.Booster
    forest: RandomForestRegressor
    ridge: Ridge
    mlp: MLPRegressor
    ridge_alpha: float
    mlp_epochs: int
    seconds: dict[str, float]


def fit_models(matrix: np.ndarray, dense: np.ndarray, target: np.ndarray, split: Split) -> Trained:
    """4モデルを順に学習し, それぞれの所要時間を測る。

    Args:
        matrix: LightGBM と RandomForest が使う 259列の行列。
        dense: Ridge と MLP が使う one-hot 展開済みの行列。
        target: 全行の pv_score。
        split: 行マスク。

    Returns:
        学習済みモデルと学習秒数。
    """
    clock = time.perf_counter()
    booster = train_lgbm(matrix, target, split)
    seconds = {"lgbm": time.perf_counter() - clock}

    clock = time.perf_counter()
    forest = train_forest(matrix, target, split)
    seconds["forest"] = time.perf_counter() - clock

    clock = time.perf_counter()
    ridge, alpha = train_ridge(dense, target, split)
    seconds["ridge"] = time.perf_counter() - clock

    clock = time.perf_counter()
    mlp, epochs = train_mlp(dense, target, split)
    seconds["mlp"] = time.perf_counter() - clock

    return Trained(booster, forest, ridge, mlp, alpha, epochs, seconds)


def run(split_name: str, seed: int) -> dict[str, float | int | str]:
    """1つの分割で4モデルを学習して artifacts に保存する。

    Args:
        split_name: "random" か "temporal"。
        seed: ランダム分割の種。

    Returns:
        artifacts/<split>/meta.json に書いた内容。
    """
    corpus, vectors = load_corpus()
    split = make_split(split_name, corpus, seed)
    target = corpus["pv_score"].to_numpy()
    matrix = feature_matrix(corpus, vectors)
    print(f"[{split_name}] {split.sizes()}")

    encoder = features.DenseEncoder.fit(matrix[split.train])
    dense = encoder.transform(matrix)
    trained = fit_models(matrix, dense, target, split)

    directory = ARTIFACT_DIR / split_name
    directory.mkdir(parents=True, exist_ok=True)
    trained.booster.save_model(str(directory / "lgbm.txt"), num_iteration=trained.booster.best_iteration)
    joblib.dump(trained.forest, directory / "forest.joblib")
    joblib.dump(trained.ridge, directory / "ridge.joblib")
    joblib.dump(trained.mlp, directory / "mlp.joblib")
    joblib.dump(encoder, directory / "encoder.joblib")

    valid_target = target[split.valid]
    meta: dict[str, float | int | str] = {
        "split": split_name,
        "seed": seed,
        "features": len(features.FEATURE_NAMES),
        "lgbm_rounds": int(trained.booster.best_iteration),
        "forest_trees": FOREST_TREES,
        "ridge_alpha": trained.ridge_alpha,
        "mlp_epochs": trained.mlp_epochs,
        "valid_spearman_lgbm": spearman(trained.booster.predict(matrix[split.valid]), valid_target),
        "valid_spearman_forest": spearman(trained.forest.predict(matrix[split.valid]), valid_target),
        "valid_spearman_ridge": spearman(trained.ridge.predict(dense[split.valid]), valid_target),
        "valid_spearman_mlp": spearman(trained.mlp.predict(dense[split.valid]), valid_target),
        **{f"seconds_{name}": value for name, value in trained.seconds.items()},
        **split.sizes(),
    }
    (directory / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def main() -> None:
    """コマンドラインから学習を回す。"""
    parser = argparse.ArgumentParser(description="pv_score を予測するモデルを学習する")
    parser.add_argument("--split", choices=[*SPLIT_NAMES, DEPLOY_SPLIT, "all"], default="all")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    targets = (*SPLIT_NAMES, DEPLOY_SPLIT) if args.split == "all" else (args.split,)
    for name in targets:
        run(name, args.seed)


if __name__ == "__main__":
    main()
