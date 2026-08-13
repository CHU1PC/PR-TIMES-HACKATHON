# デプロイ

`main` に push すると [.github/workflows/deploy.yml](../.github/workflows/deploy.yml) が全部やる。
AWS 側の初回セットアップは [infra/README.md](../infra/README.md)、環境の identifier は [infra.md](infra.md)。

## 構成

```text
ブラウザ → CloudFront ─┬─ /*      → S3(フロントの dist)
                        └─ /api/*  → ALB → ECS Fargate(FastAPI :8000)
                                              ├→ RDS + pgvector(コーパス検索)
                                              └→ OpenAI API(埋め込みと生成)
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
`127.0.0.1:15434` に向ける([infra.md](infra.md) の「手元から RDS を見る」)。
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

`db` と `migrate` も一緒に立つので, これだけで API が応答する。踏み台のトンネルは要らない。
コーパスは入らないので `/api/proposal` は空を返す。本番の RDS を見たい場合だけ
`.env` に `DATABASE_URL` を書いてトンネルを張る。

```bash
docker compose down -v   # DB のデータごと捨てる
```

## デプロイされるもの

`main` への push(または Actions タブから手動実行)で、この順に走る。

| # | 内容 |
| --- | --- |
| 1 | ruff / pytest / `tsc --noEmit` |
| 2 | `ecr` スタックを作る(無ければ) |
| 3 | イメージをビルドして ECR へ push(タグは git sha の先頭12桁) |
| 4 | `waf` スタックを流す(us-east-1) |
| 5 | **`alembic upgrade head` を ECS の使い捨てタスクで流す。落ちたらここで止まる** |
| 6 | `app` スタックを流す。イメージのタグが変わるのでタスク定義が新しくなりサービスが入れ替わる |
| 7 | フロントをビルドして S3 へ同期、CloudFront のキャッシュを飛ばす |
| 8 | `/api/health` が返るまで最大150秒待つ |

**5 が 6 より前なのは意図的。** 逆にすると新しいコードが旧スキーマの上で動き出してから
migration が走るので、そこで落ちると「新コード + 旧スキーマ」で取り残される。
この順なら migration の失敗はデプロイの中断で済み、本番は旧コード旧スキーマのまま生き残る。

URL は Actions の実行サマリに出る。

**`db` スタックは CI では流さない。** DB の作り直しはデプロイのたびに起きてよいことではない。

## migration

デプロイのたびに CI が当てる。RDS は VPC の外から届かないので、本番と同じイメージを
ECS の使い捨てタスク(`prtimes-hackathon-2026summer-migrate`)として VPC の中で起こし、
`alembic upgrade head` を流す。終了コードが 0 でなければサービスは入れ替えずに止まる。
ログは `/ecs/prtimes-hackathon-2026summer-backend` の `migrate/` ストリームに出る。

モデルを変えたら migration を作って一緒にコミットする。

```bash
cd backend && uv run alembic revision --autogenerate -m "add users and sessions"
```

**列の削除・改名は同じデプロイに混ぜない。** migration はサービスの入れ替えより先に終わるので、
旧コードが数十秒だけ新しいスキーマの上で動く。追加だけに保てばここは無害だが、
消す変更は「新コードが参照をやめる」→ デプロイ → 「列を消す」の2回に分ける。

### 本番のコピーに当てて確かめる

順番を直したので migration の失敗で本番が壊れることはないが、**失敗すること自体は防げない。**
空の DB では通る DDL が、本番の 129,045 行では落ちる(NOT NULL の追加、ユニーク制約違反、型変換)。
追加以外の migration を書いたら、merge の前にスナップショットから起こしたコピーで試す。
**本番インスタンスは読まないので、稼働中のサービスには影響しない。**

```bash
snap=$(aws rds describe-db-snapshots --db-instance-identifier prtimes-hackathon-2026summer-app \
  --query 'reverse(sort_by(DBSnapshots,&SnapshotCreateTime))[0].DBSnapshotIdentifier' --output text)

aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier prtimes-hackathon-2026summer-migcheck \
  --db-snapshot-identifier "$snap" \
  --db-instance-class db.t4g.small \
  --db-subnet-group-name prtimes-hackathon-2026summer-app \
  --vpc-security-group-ids "$(aws cloudformation describe-stacks --stack-name prtimes-hackathon-db \
    --query 'Stacks[0].Outputs[?OutputKey==`SecurityGroupId`].OutputValue' --output text)" \
  --no-publicly-accessible
aws rds wait db-instance-available --db-instance-identifier prtimes-hackathon-2026summer-migcheck
```

復元に15〜20分かかる。立ったら踏み台越しにトンネルを張って当てる(パスワードは本番と同じ)。

```bash
ep=$(aws rds describe-db-instances --db-instance-identifier prtimes-hackathon-2026summer-migcheck \
  --query 'DBInstances[0].Endpoint.Address' --output text)
ssh -i ~/.ssh/prtimes/hackathon.pem -N -f -L "15435:$ep:5432" ubuntu@13.112.91.188

cd backend
DATABASE_URL="postgresql://prtimes:${PW}@127.0.0.1:15435/app" uv run alembic upgrade head
```

通ったら捨てる。**消し忘れると課金が続く。**

```bash
aws rds delete-db-instance --db-instance-identifier prtimes-hackathon-2026summer-migcheck \
  --skip-final-snapshot
```

手元から本番に当てる場合も踏み台越し([infra/README.md](../infra/README.md))。

## 止める

タスクの課金だけ止めるなら `DesiredCount=0`([infra/README.md](../infra/README.md))。

## 詰まったとき

| 症状 | 見るところ |
| --- | --- |
| タスクが起動と停止を繰り返す | CloudWatch Logs `/ecs/prtimes-hackathon-2026summer-backend`。キーの取得失敗が多い |
| ターゲットが unhealthy のまま | ヘルスチェックは `/api/health`。ルータの prefix を変えたら合わせる |
| `/api/*` が 403 | CloudFront の `/api/*` ビヘイビアが ALB を向いているか。S3 側に落ちていないか |
| 画面は出るが API だけ 404 | S3 の `CustomErrorResponses`(403→index.html)に吸われている。ALB 側の応答を直接確かめる |
| デプロイが `UnauthorizedOperation` | IAM ポリシーが古い。エラーが名指しするアクションを足す |

ALB を直接叩いて切り分けたいときは、SG が CloudFront 以外を弾くので**一時的に自分の IP を足す**。
確認が終わったら必ず消すこと。
