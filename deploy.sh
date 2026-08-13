#!/usr/bin/env bash
# フロントを S3 へ, バックエンドを EC2 へ配る. 第1引数で鍵のパスを受ける
set -euo pipefail

KEY="${1:-$HOME/.ssh/prtimes/hackathon.pem}"
HOST="ubuntu@13.112.91.188"
REMOTE_DIR="/home/ubuntu/prtimes-hackathon"
PROFILE="${AWS_PROFILE:-prtimes}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$KEY" ]] || { echo "鍵が無い: $KEY" >&2; exit 1; }
[[ -f "$REPO_ROOT/.env" ]] || { echo ".env が無い. .env.example をコピーして値を埋める" >&2; exit 1; }

# 600 以外だと ssh が鍵を拒否する
chmod 600 "$KEY"

SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new)

echo "==> [1/6] Terraform の出力を読む"
cd "$REPO_ROOT/infra"
BUCKET="$(terraform output -raw frontend_bucket)"
DISTRIBUTION="$(terraform output -raw distribution_id)"
APP_URL="$(terraform output -raw app_url)"
cd "$REPO_ROOT"
echo "    bucket=$BUCKET distribution=$DISTRIBUTION"

echo "==> [2/6] フロントをビルド"
# VITE_API_BASE は空にする. CloudFront が /api/* を EC2 へ回すので同一オリジンで届く
cd "$REPO_ROOT/frontend"
VITE_API_BASE="" bun run build
cd "$REPO_ROOT"

echo "==> [3/6] S3 へ同期"
# 内容ハッシュ付きの assets は長期キャッシュ, index.html は毎回取り直させる
aws s3 sync frontend/dist "s3://$BUCKET" --profile "$PROFILE" --delete \
  --exclude 'index.html' --cache-control 'public,max-age=31536000,immutable'
aws s3 cp frontend/dist/index.html "s3://$BUCKET/index.html" --profile "$PROFILE" \
  --cache-control 'no-cache'

echo "==> [4/6] バックエンドを EC2 へ転送"
"${SSH[@]}" "$HOST" "mkdir -p '$REMOTE_DIR'"
# data/ は 700MB 超の DuckDB. frontend は S3 に載せたのでもう要らない
rsync -az --delete \
  -e "${SSH[*]}" \
  --exclude '.git/' \
  --exclude '.hermes/' \
  --exclude 'infra/' \
  --exclude 'frontend/' \
  --exclude 'data/' \
  --exclude '.venv/' \
  --exclude 'node_modules/' \
  --exclude '__pycache__/' \
  --exclude '.ruff_cache/' \
  --exclude '.pytest_cache/' \
  --exclude '.env' \
  "$REPO_ROOT/" "$HOST:$REMOTE_DIR/"

# .env は git 管理外なので rsync の対象外. 毎回上書きして値のズレを防ぐ
scp -i "$KEY" -o StrictHostKeyChecking=accept-new "$REPO_ROOT/.env" "$HOST:$REMOTE_DIR/.env"

echo "==> [5/6] EC2 で build & up"
# ubuntu ユーザーは docker グループに入っていないので sudo が要る
"${SSH[@]}" "$HOST" "cd '$REMOTE_DIR' && sudo docker compose up -d --build"

echo "==> [6/6] CloudFront のキャッシュを消して疎通確認"
aws cloudfront create-invalidation --profile "$PROFILE" \
  --distribution-id "$DISTRIBUTION" --paths '/*' >/dev/null

# uv の起動 + langchain の import で数十秒かかることがあるのでリトライする
for _ in $(seq 1 20); do
  if body="$(curl -fsS --max-time 10 "$APP_URL/api/health" 2>/dev/null)"; then
    echo "OK: $body"
    echo
    echo "デモ URL: $APP_URL"
    exit 0
  fi
  sleep 5
done

echo "NG: $APP_URL/api/health が応答しない" >&2
"${SSH[@]}" "$HOST" "cd '$REMOTE_DIR' && sudo docker compose logs --tail 50"
exit 1
