# デプロイ手順

EC2 (`13.112.91.188`) の **8080 番**に、FastAPI + Vite ビルド成果物を 1 コンテナで載せる。
インフラの詳細は `docs/infra.md` を参照。

## 構成

| ファイル | 役割 |
|---|---|
| `backend/Dockerfile` | 3 ステージ（bun でフロントをビルド → uv で Python 依存 → 実行） |
| `docker-compose.yml` | サービス 1 つ。`8080:8080` で公開 |
| `deploy.sh` | ローカル → EC2 の rsync + build + 疎通確認 |

FastAPI が `frontend/dist` を同一オリジンで配信するため nginx は要らない。
`app/settings/paths.py` の `ROOT = parents[3]` に合わせ、コンテナ内は
`/app/backend`（アプリ）と `/app/frontend/dist`（静的ファイル）に配置している。

## 前提

- **80 番は pgAdmin (gunicorn) が使用中。絶対に潰さない**
- `ubuntu` ユーザーは docker グループに入っていないので `sudo docker compose` で叩く
- 自宅などから作業する場合、IP が変わったらセキュリティグループを更新する
  （`curl -4 -s ifconfig.me` → `docs/infra.md` の `authorize-security-group-ingress`）

## 1. `.env` を用意する

`.env` は **git に入れない**。`.env.example` をコピーして値を埋める。

```bash
cp .env.example .env
```

EC2 用に 2 つ書き換える。

| キー | ローカル | EC2 |
|---|---|---|
| `DATABASE_URL` | `...@127.0.0.1:15432/prtimes`（SSH トンネル） | RDS エンドポイントを直接（同一 VPC のためトンネル不要） |
| `ALLOWED_ORIGINS` | `'["http://localhost:5173"]'` | `'["http://13.112.91.188:8080"]'` |

`deploy.sh` が `.env` を毎回 scp で送るので、手動転送は不要。
手で送る場合は次のとおり。**rsync は `.env` を除外している**（`--delete` で消さないため）。

```bash
scp -i ~/.ssh/prtimes/hackathon.pem .env ubuntu@13.112.91.188:/home/ubuntu/prtimes-hackathon/.env
```

## 2. デプロイする

```bash
./deploy.sh                          # 鍵は ~/.ssh/prtimes/hackathon.pem
./deploy.sh /path/to/other-key.pem   # 鍵を指定する場合
```

やっていること。

1. `rsync` でソースを `/home/ubuntu/prtimes-hackathon/` へ同期
   （`data/` `.venv/` `node_modules/` `dist/` `.git/` は送らない）
2. `.env` を scp
3. EC2 上で `sudo docker compose up -d --build`
4. `http://13.112.91.188:8080/api/health` を最大 60 秒リトライして確認

成功すると `OK: {"ok":true}` が出る。失敗すると直近 50 行のログを表示して終了する。

## 3. 手で操作する

```bash
ssh -i ~/.ssh/prtimes/hackathon.pem ubuntu@13.112.91.188
cd /home/ubuntu/prtimes-hackathon

sudo docker compose ps            # 状態 (health も出る)
sudo docker compose logs -f       # ログ追尾
sudo docker compose restart       # 再起動 (ビルドし直さない)
sudo docker compose up -d --build # 再ビルドして入れ替え
sudo docker compose down          # 停止して 8080 を空ける
```

## 4. ロールバック

イメージは `prtimes-hackathon-app:latest` に上書きされるので、**戻したいコミットから
ビルドし直す**のが確実。

```bash
git checkout <戻したいコミット>
./deploy.sh
git checkout main
```

デモ直前など、確実に戻したい版がある場合は入れ替え前にタグを退避しておく。

```bash
# EC2 上で、build する前に現行イメージを退避
sudo docker tag prtimes-hackathon-app:latest prtimes-hackathon-app:rollback

# 戻すとき
sudo docker compose down
sudo docker tag prtimes-hackathon-app:rollback prtimes-hackathon-app:latest
sudo docker compose up -d --no-build
```

とにかく止めたいときは `sudo docker compose down`。80 番の pgAdmin には影響しない。

## トラブルシュート

**`ALLOWED_ORIGINS` のパースで落ちる**

`.env` の値はシングルクォートで囲っている。compose の `env_file:` はクォートを剥がすが、
`docker run --env-file` は**剥がさない**ためそのまま渡って JSON パースに失敗する。
ローカルで単体起動して確認したいときは `docker compose up` を使うか、
`-e 'ALLOWED_ORIGINS=["http://localhost:8080"]'` で個別に渡す。

**ssh がタイムアウトする**

IP が変わってセキュリティグループから外れている。`docs/infra.md` の手順で再登録する。

**ビルドが遅い / メモリが足りない**

t3.medium は 2 vCPU / 3.7GB を pgAdmin と分け合う。不要なイメージが溜まっていたら
`sudo docker system prune -f` で掃除する（`data/` は転送していないのでディスクは
主にイメージが食っている）。

**8080 が既に使われている**

`sudo ss -tlnp | grep 8080` で確認。自分の古いコンテナなら `sudo docker compose down`。
