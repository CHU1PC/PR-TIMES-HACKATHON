from pathlib import Path

# predict.py が pandas を引かずに済むよう, パス定数だけを標準ライブラリで持つ
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CORPUS_PATH = DATA_DIR / "corpus.parquet"
VECTOR_PATH = DATA_DIR / "corpus_vec.npy"

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"

# 評価に使う2つの分割と, 全期間で学習して本番に載せる1つ
SPLIT_NAMES = ("random", "temporal")
DEPLOY_SPLIT = "deploy"
DEPLOY_MODEL_PATH = ARTIFACT_DIR / DEPLOY_SPLIT / "lgbm.txt"
