#!/usr/bin/env bash
# ローカルから EC2 へデプロイする. 第1引数で鍵のパスを受ける
set -euo pipefail

KEY="${1:-$HOME/.ssh/prtimes/hackathon.pem}"
HOST="ubuntu@13.112.91.188"
REMOTE_DIR="/home/ubuntu/prtimes-hackathon"
HEALTH_URL="http://13.112.91.188:8080/api/health"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$KEY" ]] || { echo "鍵が無い: $KEY" >&2; exit 1; }
[[ -f "$REPO_ROOT/.env" ]] || { echo ".env が無い. .env.example をコピーして値を埋める" >&2; exit 1; }

# 600 以外だと ssh が鍵を拒否する
chmod 600 "$KEY"

SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new)

echo "==> [1/4] 転送先を用意: $HOST:$REMOTE_DIR"
"${SSH[@]}" "$HOST" "mkdir -p '$REMOTE_DIR'"

echo "==> [2/4] rsync"
# data/ は 700MB 超の DuckDB. .venv と node_modules と dist は EC2 のビルドで作り直す.
# .env は --delete で消されないよう除外し, 直後に scp で別途送る
rsync -az --delete \
  -e "${SSH[*]}" \
  --exclude '.git/' \
  --exclude '.hermes/' \
  --exclude 'data/' \
  --exclude '.venv/' \
  --exclude 'node_modules/' \
  --exclude 'dist/' \
  --exclude '__pycache__/' \
  --exclude '.ruff_cache/' \
  --exclude '.pytest_cache/' \
  --exclude '.env' \
  "$REPO_ROOT/" "$HOST:$REMOTE_DIR/"

# .env は git 管理外なので rsync の対象外. 毎回上書きして値のズレを防ぐ
scp -i "$KEY" -o StrictHostKeyChecking=accept-new "$REPO_ROOT/.env" "$HOST:$REMOTE_DIR/.env"

echo "==> [3/4] build & up"
# ubuntu ユーザーは docker グループに入っていないので sudo が要る
"${SSH[@]}" "$HOST" "cd '$REMOTE_DIR' && sudo docker compose up -d --build"

echo "==> [4/4] 疎通確認: $HEALTH_URL"
# uv の起動 + langchain の import で数十秒かかることがあるのでリトライする
for _ in $(seq 1 20); do
  if body="$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null)"; then
    echo "OK: $body"
    exit 0
  fi
  sleep 3
done

echo "NG: $HEALTH_URL が応答しない" >&2
"${SSH[@]}" "$HOST" "cd '$REMOTE_DIR' && sudo docker compose logs --tail 50"
exit 1
