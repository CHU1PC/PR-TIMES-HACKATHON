from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[3]

# ETL の出力と DuckDB。RDS 由来のデータなので git 管理外
DATA_DIR: Final = ROOT / "data"
