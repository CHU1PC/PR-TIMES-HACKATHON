from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.features import MISSING_CATEGORY, PRESENCE_KEYWORDS, build_matrix
from ml.paths import CORPUS_PATH, DEPLOY_SPLIT, VECTOR_PATH

# corpus_vec.npy は corpus.parquet と同じ行順(ORDER BY company_id, release_id)なので, 並べ替えずに読む
CORPUS_COLUMNS = [
    "company_id",
    "release_id",
    "created_at",
    "title",
    "business_category_id",
    "prefecture_id",
    "release_type_id",
    "pv_score",
]

TEST_FRACTION = 0.2
VALID_FRACTION = 0.1
RANDOM_SEED = 20260814


@dataclass(frozen=True)
class Split:
    """train/valid/test の行マスク。"""

    name: str
    train: np.ndarray
    valid: np.ndarray
    test: np.ndarray

    def sizes(self) -> dict[str, int]:
        """各マスクの行数を返す。

        Returns:
            train/valid/test/dropped の行数。
        """
        used = int(self.train.sum() + self.valid.sum() + self.test.sum())
        return {
            "train": int(self.train.sum()),
            "valid": int(self.valid.sum()),
            "test": int(self.test.sum()),
            "dropped": len(self.train) - used,
        }


def load_corpus() -> tuple[pd.DataFrame, np.ndarray]:
    """コーパスと埋め込みを読む。

    Returns:
        必要列だけの DataFrame と, 同じ行順の (件数, 256) ベクトル。

    Raises:
        ValueError: parquet と npy の行数が食い違うとき。
    """
    corpus = pd.read_parquet(CORPUS_PATH, columns=CORPUS_COLUMNS)
    vectors = np.load(VECTOR_PATH)
    if len(corpus) != len(vectors):
        msg = f"行数が合わない corpus={len(corpus)} vectors={len(vectors)}"
        raise ValueError(msg)
    return corpus, vectors


def _split_by_time(company_id: np.ndarray, created_at: np.ndarray, keep: float) -> tuple[np.ndarray, np.ndarray]:
    """時刻で前後に切り, 後半は前半に出てこない企業だけ残す。

    Args:
        company_id: 行ごとの企業ID。
        created_at: 行ごとの公開日時。
        keep: 前半に入れる行の割合。

    Returns:
        前半と後半の行マスク。どちらにも入らない行(前半企業の未来のリリース)は捨てる。
    """
    stamps = created_at.astype("datetime64[ns]").astype("int64")
    cutoff = np.quantile(stamps, keep)
    past = stamps < cutoff
    future = ~past & ~np.isin(company_id, company_id[past])
    return past, future


def temporal_split(company_id: np.ndarray, created_at: np.ndarray) -> Split:
    """古い期間で学習し, 新しい期間の新規企業で検証する分割を作る。

    Args:
        company_id: 行ごとの企業ID。
        created_at: 行ごとの公開日時。

    Returns:
        train/valid/test の行マスク。
    """
    pool, test = _split_by_time(company_id, created_at, 1.0 - TEST_FRACTION)
    pool_index = np.flatnonzero(pool)
    inner_keep = 1.0 - VALID_FRACTION / (1.0 - TEST_FRACTION)
    inner_train, inner_valid = _split_by_time(company_id[pool_index], created_at[pool_index], inner_keep)

    train = np.zeros(len(company_id), dtype=bool)
    valid = np.zeros(len(company_id), dtype=bool)
    train[pool_index[inner_train]] = True
    valid[pool_index[inner_valid]] = True
    return Split(name="temporal", train=train, valid=valid, test=test)


def deploy_split(company_id: np.ndarray, seed: int = RANDOM_SEED) -> Split:
    """本番に載せる用。test を作らず, 早期終了の回数を決めるためだけに 10% を残す。

    Args:
        company_id: 行ごとの企業ID。
        seed: シャッフルの種。

    Returns:
        test が空の行マスク。

    Note:
        時系列で valid を切ると新規企業が 2,164行しか残らず, 木が 127本で止まって
        本番モデルだけ学習不足になった。汎化は測らない場所なので企業ランダムに戻す。
    """
    companies = np.unique(company_id)
    np.random.default_rng(seed).shuffle(companies)
    valid = np.isin(company_id, companies[: int(len(companies) * VALID_FRACTION)])
    return Split(name=DEPLOY_SPLIT, train=~valid, valid=valid, test=np.zeros(len(company_id), dtype=bool))


def random_split(company_id: np.ndarray, seed: int = RANDOM_SEED) -> Split:
    """企業単位でランダムに分割する。行単位で切ると同じ企業が train と test に跨る。

    Args:
        company_id: 行ごとの企業ID。
        seed: シャッフルの種。

    Returns:
        train/valid/test の行マスク。
    """
    companies = np.unique(company_id)
    np.random.default_rng(seed).shuffle(companies)
    test_end = int(len(companies) * TEST_FRACTION)
    valid_end = int(len(companies) * (TEST_FRACTION + VALID_FRACTION))

    test = np.isin(company_id, companies[:test_end])
    valid = np.isin(company_id, companies[test_end:valid_end])
    return Split(name="random", train=~(test | valid), valid=valid, test=test)


def make_split(name: str, corpus: pd.DataFrame, seed: int = RANDOM_SEED) -> Split:
    """名前で分割を作り分ける。

    Args:
        name: "random" か "temporal"。
        corpus: load_corpus() の DataFrame。
        seed: ランダム分割の種。

    Returns:
        train/valid/test の行マスク。

    Raises:
        ValueError: 未知の分割名のとき。
    """
    company_id = corpus["company_id"].to_numpy()
    if name == "random":
        return random_split(company_id, seed)
    if name == "temporal":
        return temporal_split(company_id, corpus["created_at"].to_numpy())
    if name == DEPLOY_SPLIT:
        return deploy_split(company_id, seed)
    msg = f"未知の分割 {name}"
    raise ValueError(msg)


def presence_flags(titles: pd.Series) -> np.ndarray:
    """タイトル列をまとめて存在告知フラグにする。

    Args:
        titles: タイトルの列。

    Returns:
        0/1 の float32 配列。
    """
    pattern = "|".join(PRESENCE_KEYWORDS)
    return titles.fillna("").str.contains(pattern, regex=True).to_numpy().astype(np.float32)


def feature_matrix(corpus: pd.DataFrame, vectors: np.ndarray) -> np.ndarray:
    """コーパスの行から, 推論側と同じ列順の特徴行列を組む。

    Args:
        corpus: load_corpus() の DataFrame。
        vectors: 同じ行順の埋め込み。

    Returns:
        (件数, 259) の float32 行列。
    """
    return build_matrix(
        vectors,
        corpus["business_category_id"].fillna(MISSING_CATEGORY).to_numpy(),
        corpus["prefecture_id"].fillna(MISSING_CATEGORY).to_numpy(),
        presence_flags(corpus["title"]),
    )
