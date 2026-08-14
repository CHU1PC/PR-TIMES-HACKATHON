from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

# 予定を並べる単位。1ヶ月ぶんの候補から上位10件を選ぶ, という本番の使い方に合わせる
GROUP_SIZE = 20
NDCG_K = 10
COMPANY_MIN_ROWS = 10


def rmse(predicted: np.ndarray, actual: np.ndarray) -> float:
    """二乗平均平方根誤差。

    Args:
        predicted: 予測値。
        actual: 実測値。

    Returns:
        RMSE。
    """
    return float(np.sqrt(np.mean((predicted - actual) ** 2)))


def spearman(predicted: np.ndarray, actual: np.ndarray) -> float:
    """Spearman 順位相関。

    Args:
        predicted: 予測値。
        actual: 実測値。

    Returns:
        相関係数。
    """
    return float(spearmanr(predicted, actual).statistic)


def ndcg_at_k(predicted: np.ndarray, actual: np.ndarray, k: int = NDCG_K) -> float:
    """1グループの NDCG@k。pv_score は 0〜1 なので gain はそのまま使う。

    Args:
        predicted: グループ内の予測値。
        actual: グループ内の pv_score。
        k: 上位いくつを見るか。

    Returns:
        0〜1 の NDCG。
    """
    size = min(k, len(actual))
    discount = 1.0 / np.log2(np.arange(2, size + 2))
    gains = actual[np.argsort(-predicted, kind="stable")][:size]
    ideal = np.sort(actual)[::-1][:size]
    best = float(np.sum(ideal * discount))
    return float(np.sum(gains * discount)) / best if best > 0 else 0.0


def grouped_ndcg(predicted: np.ndarray, actual: np.ndarray, groups: list[np.ndarray], k: int = NDCG_K) -> float:
    """グループごとの NDCG@k を平均する。

    Args:
        predicted: 全体の予測値。
        actual: 全体の pv_score。
        groups: グループごとの行番号。
        k: 上位いくつを見るか。

    Returns:
        平均 NDCG。グループが無ければ 0。
    """
    if not groups:
        return 0.0
    return float(np.mean([ndcg_at_k(predicted[g], actual[g], k) for g in groups]))


def random_groups(size: int, group_size: int = GROUP_SIZE, seed: int = 0) -> list[np.ndarray]:
    """テスト行をシャッフルして固定長のグループに刻む。

    Args:
        size: テスト行数。
        group_size: 1グループの件数。
        seed: シャッフルの種。

    Returns:
        グループごとの行番号。端数は捨てる。
    """
    order = np.random.default_rng(seed).permutation(size)
    count = size // group_size
    return [order[i * group_size : (i + 1) * group_size] for i in range(count)]


def company_groups(company_id: np.ndarray, min_rows: int = COMPANY_MIN_ROWS) -> list[np.ndarray]:
    """同じ企業の行をグループにする。件数が足りない企業は落とす。

    Args:
        company_id: テスト行の企業ID。
        min_rows: グループに必要な最小件数。

    Returns:
        グループごとの行番号。
    """
    order = np.argsort(company_id, kind="stable")
    boundaries = np.flatnonzero(np.diff(company_id[order])) + 1
    chunks = np.split(order, boundaries)
    return [c for c in chunks if len(c) >= min_rows]


def bootstrap_gap(
    challenger: np.ndarray,
    incumbent: np.ndarray,
    actual: np.ndarray,
    rounds: int = 1000,
    seed: int = 0,
) -> tuple[float, float]:
    """2つの予測の Spearman 差を, 同じ行を選び直して 95% 区間で挟む。

    Args:
        challenger: 比べたい側の予測。
        incumbent: 比べられる側の予測。
        actual: テスト行の pv_score。
        rounds: 再標本の回数。
        seed: 再標本の種。

    Returns:
        差の 2.5% 点と 97.5% 点。0 をまたがなければ有意。
    """
    rng = np.random.default_rng(seed)
    size = len(actual)
    gaps = np.empty(rounds)
    for i in range(rounds):
        pick = rng.integers(0, size, size)
        gaps[i] = spearman(challenger[pick], actual[pick]) - spearman(incumbent[pick], actual[pick])
    return float(np.percentile(gaps, 2.5)), float(np.percentile(gaps, 97.5))


def report(predicted: np.ndarray, actual: np.ndarray, company_id: np.ndarray) -> dict[str, float]:
    """1つの予測に対して指標を一式出す。

    Args:
        predicted: テスト行の予測値。
        actual: テスト行の pv_score。
        company_id: テスト行の企業ID。

    Returns:
        指標名から値への辞書。
    """
    companies = company_groups(company_id)
    return {
        "spearman": spearman(predicted, actual),
        "ndcg@10_random20": grouped_ndcg(predicted, actual, random_groups(len(actual))),
        "ndcg@10_company": grouped_ndcg(predicted, actual, companies),
        "company_groups": float(len(companies)),
        "rmse": rmse(predicted, actual),
    }
