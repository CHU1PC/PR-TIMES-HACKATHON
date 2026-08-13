# デプロイ

`main` に push すると [.github/workflows/deploy.yml](../.github/workflows/deploy.yml) が全部やる。
AWS 側の初回セットアップは [infra/README.md](../infra/README.md)、環境の identifier は [infra.md](infra.md)。

## 構成

```text
ブラウザ → CloudFront ─┬─ /*      → S3（フロントの dist）
                        └─ /api/*  → ALB → ECS Fargate（FastAPI :8000）
                                              ├→ RDS + pgvector（コーパス検索）
                                              └→ OpenAI API（埋め込みと生成）
```

フロントとバックエンドは**同一オリジン**で配られる。本番で CORS は効かない。

## 手元で動かす

コンテナは要らない。バックエンドとフロントを別々に起動する。

```bash
# ターミナル1: バックエンド (:8000)
cd backend && uv run --env-file ../.env fastapi dev

# ターミナル2: フロント (:5173)
cd frontend && bun run dev
```

`proposal` 機能は RDS を読むので、事前に SSH トンネルを張って `.env` の `DATABASE_URL` を
`127.0.0.1:15434` に向ける（[infra.md](infra.md) の「手元から RDS を見る」）。
壁打ちとヒアリングだけなら DB は要らない。

`.env` に要るのは3つ。

| 変数 | 用途 |
| --- | --- |
| `OPENAI_API_KEY` | 壁打ち・ヒアリング・提案・埋め込み |
| `DATABASE_URL` | コーパス検索。トンネル経由 |
| `ALLOWED_ORIGINS` | dev は `'["http://localhost:5173"]'` |

本番と同じイメージを手元で確かめるときだけ compose を使う。

```bash
docker compose up --build
```

## デプロイされるもの

`main` への push（または Actions タブから手動実行）で、この順に走る。

| # | 内容 |
| --- | --- |
| 1 | ruff / pytest / `tsc --noEmit` |
| 2 | イメージをビルドして ECR へ push（タグは git sha の先頭12桁） |
| 3 | `ecr` スタックを作る（無ければ） |
| 4 | `app` スタックを流す。イメージのタグが変わるのでタスク定義が新しくなりサービスが入れ替わる |
| 5 | `alembic upgrade head` を ECS の使い捨てタスクで流す。落ちたらここで止まる |
| 6 | フロントをビルドして S3 へ同期、CloudFront のキャッシュを飛ばす |
| 7 | `/api/health` が返るまで最大150秒待つ |

URL は Actions の実行サマリに出る。

**`db` スタックは CI では流さない。** DB の作り直しはデプロイのたびに起きてよいことではない。

## migration

デプロイのたびに CI が当てる。RDS は VPC の外から届かないので、本番と同じイメージを
ECS の使い捨てタスク（`prtimes-hackathon-2026summer-migrate`）として VPC の中で起こし、
`alembic upgrade head` を流す。終了コードが 0 でなければサービスは入れ替えずに止まる。
ログは `/ecs/prtimes-hackathon-2026summer-backend` の `migrate/` ストリームに出る。

モデルを変えたら migration を作って一緒にコミットする。

```bash
cd backend && uv run alembic revision --autogenerate -m "add users and sessions"
```

**列の削除・改名は同じデプロイに混ぜない。** マイグレーションはサービスの入れ替えより
先に終わるので、旧コードが数十秒だけ新しいスキーマの上で動く。追加だけに保てばここは無害だが、
消す変更は「新コードが参照をやめる」→ デプロイ → 「列を消す」の2回に分ける。

手元から当てる場合は踏み台越しにトンネルを張る（[infra/README.md](../infra/README.md)）。

## 止める

タスクの課金だけ止めるなら `DesiredCount=0`（[infra/README.md](../infra/README.md)）。

## 詰まったとき

| 症状 | 見るところ |
| --- | --- |
| タスクが起動と停止を繰り返す | CloudWatch Logs `/ecs/prtimes-hackathon-2026summer-backend`。キーの取得失敗が多い |
| ターゲットが unhealthy のまま | ヘルスチェックは `/api/health`。ルータの prefix を変えたら合わせる |
| `/api/*` が 403 | CloudFront の `/api/*` ビヘイビアが ALB を向いているか。S3 側に落ちていないか |
| 画面は出るが API だけ 404 | S3 の `CustomErrorResponses`（403→index.html）に吸われている。ALB 側の応答を直接確かめる |
| デプロイが `UnauthorizedOperation` | IAM ポリシーが古い。エラーが名指しするアクションを足す |

ALB を直接叩いて切り分けたいときは、SG が CloudFront 以外を弾くので**一時的に自分の IP を足す**。
確認が終わったら必ず消すこと。
