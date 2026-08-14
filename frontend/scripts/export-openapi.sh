#!/bin/sh
# backend の FastAPI から openapi.json を書き出す。DB にも外部にも繋がない。
set -eu

here=$(cd "$(dirname "$0")" && pwd)
backend="$here/../../backend"
out="$here/../openapi.json"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv が要ります: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

cd "$backend"

# app.llm が import 時に ChatOpenAI を組み立て, キーの有無だけ見る。生成に通信は使わない
OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}" uv run python - "$out" <<'PY'
import json
import sys

from app.main import app

# sort_keys で並びを固定する。差分が契約の変更だけになる
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(app.openapi(), handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
PY

echo "wrote $out"
