# インフラ情報

秘密情報は含めない。パスワードとキーは Parameter Store と `.env`（git 管理外）に置く。
作成手順は [infra/README.md](../infra/README.md)、構成図は [architecture.drawio](architecture.drawio)。

## AWS

| 項目 | 値 |
| --- | --- |
| アカウント | 622952748235 (`hackathon-2026-summer-team1`) |
| リージョン | ap-northeast-1 |
| デプロイ用 IAM ユーザー | `prtimes-hackathon-deployer`（管理ポリシー `prtimes-hackathon-deploy` を直接アタッチ） |
| CI が引くロール | `prtimes-hackathon-github-actions`（OIDC。`refs/heads/main` のみ） |

## 主催者から与えられたもの（触らない）

| 種別 | 識別子 | 備考 |
| --- | --- | --- |
| VPC | `vpc-02e7854aab60dec68` / 10.0.0.0/16 | |
| パブリックサブネット 1a | `subnet-03149d1fff0e9c910` / 10.0.0.0/24 | **VPC 唯一のパブリック** |
| プライベートサブネット 1a | `subnet-0f2e3d01f6928b16d` / 10.0.10.0/24 | 既定経路なし |
| プライベートサブネット 1c | `subnet-0cda628b15e4600cf` / 10.0.20.0/24 | 既定経路なし |
| Internet Gateway | `igw-078265d20c8d0f895` | |
| EC2 | `i-0c72d1263ec5fef53` / 13.112.91.188 / SG `sg-03555db1c40d124bf` | pgAdmin(:80) と踏み台 |
| RDS | `prtimes-hackathon-2026summer-db` / SG `sg-081829ee647a0df64` | 元データ。**読み取りのみ・DDL を打たない** |

RDS は `PubliclyAccessible: false`。手元から見るには EC2 を踏み台にした SSH トンネルが要る。

## このプロジェクトで作ったもの

| スタック | 主なリソース |
| --- | --- |
| `prtimes-hackathon-oidc` | GitHub Actions 用の IAM ロールと OIDC プロバイダ |
| `prtimes-hackathon-ecr` | バックエンドのイメージ置き場（5世代保持） |
| `prtimes-hackathon-db` | アプリ用 RDS `prtimes-hackathon-2026summer-app` / SG `sg-0f770364a7919eb30` |
| `prtimes-hackathon-app` | S3 / CloudFront / ALB / ECS Fargate / ログ / ロール / **パブリックサブネット 1c**（10.0.1.0/24・自前のルートテーブルで既存 IGW へ） |

アプリ用 RDS は PostgreSQL 17.9 + pgvector 0.8.1、`db.t4g.small`、DB 名 `app`。
バックアップ1世代、`DeletionPolicy: Snapshot`。RAG のコーパス 12.9万件と転載ログ 539万行が入っている。

**既存のサブネットとルートテーブルには書き込まない。** 足りないパブリックサブネットを1枚足すだけ。
ALB は AZ 違いのサブネットが2枚必要だが、既存は 1a に1枚しかないため。

## ポート

| ポート | 用途 |
| --- | --- |
| 22 | EC2 への SSH（踏み台） |
| 80 | EC2 の pgAdmin。**潰さない** |
| 8000 | バックエンド（ローカルもコンテナも同じ） |
| 5173 | フロントの dev server |
| 5432 | RDS |

## セキュリティグループ（矢印1本 = inbound 1本）

| 対象 | 許可する inbound |
| --- | --- |
| ALB | CloudFront のマネージドプレフィックスリスト `pl-58a04531` から :80 |
| ECS タスク | ALB の SG から :8000 |
| アプリ用 RDS | タスクの SG と 踏み台 EC2 の SG から :5432 |
| 主催者の RDS | 変更しない |

NAT Gateway は置かない。タスクをパブリックサブネットに置き、SG で閉じる。
**到達できるかを決めるのは経路ではなく SG** で、ルールに合わない通信はコンテナに届く前に破棄される。

## 秘密情報の置き場

すべて Parameter Store の SecureString。値はリポジトリにもテンプレートにも CI のログにも残らない。

| パラメータ | 使う人 |
| --- | --- |
| `/prtimes-hackathon/openai-api-key` | ECS タスク（環境変数 `OPENAI_API_KEY`） |
| `/prtimes-hackathon/database-url` | ECS タスク（環境変数 `DATABASE_URL`） |
| `/prtimes-hackathon/db-password` | CloudFormation のスタック更新時 |

## 手元から RDS を見る

```bash
# アプリ用 RDS
ssh -i ~/.ssh/prtimes/hackathon.pem -N -f \
  -L 15434:prtimes-hackathon-2026summer-app.cnum2840eavk.ap-northeast-1.rds.amazonaws.com:5432 \
  ubuntu@13.112.91.188

DATABASE_URL="postgresql://prtimes:$(aws ssm get-parameter --profile prtimes \
  --region ap-northeast-1 --name /prtimes-hackathon/db-password --with-decryption \
  --query Parameter.Value --output text)@127.0.0.1:15434/app"
```

主催者の RDS を見るときはホストを `...-db...` に、ポートを 15432 に変えて同じ手順。

## EC2 のセキュリティグループ

会場外から作業するため自宅 IP を追加してある。**IP が変わったら登録し直す**（`curl -4 -s ifconfig.me`）。

```bash
aws ec2 authorize-security-group-ingress --region ap-northeast-1 --profile prtimes \
  --group-id sg-03555db1c40d124bf --protocol tcp --port 22 --cidr <IP>/32
```

22 番を `0.0.0.0/0` で開けない。

## 終了時のクリーンアップ

- [ ] `DesiredCount=0` でタスクを止める（[infra/README.md](../infra/README.md) の「止めるとき」）
- [ ] EC2 の SG から自宅 IP のルールを削除
- [ ] スタックを app → db → ecr → oidc の順で削除（S3 は中身を空にしてから）
- [ ] `prtimes-hackathon-deployer` のアクセスキーを削除
