import json
import sys
from pathlib import Path

from app.main import app

# 既定はフロントの取り込み先。kubb.config.ts の input と揃える
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    """FastAPI から openapi.json を書き出す。DB にも外部にも繋がない。"""
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    # sort_keys で並びを固定する。差分が契約の変更だけになる
    body = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True)
    out.write_text(body + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
