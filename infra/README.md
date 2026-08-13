# インフラ

[architecture.drawio](../docs/architecture.drawio) の構成を CloudFormation で作る。
環境の identifier は [../docs/infra.md](../docs/infra.md)、デプロイの流れは [../docs/deploy.md](../docs/deploy.md)。

| ファイル | 中身 | 誰が流すか |
| --- | --- | --- |
| `iam.yaml` | OIDC 信頼 / CI のロール / **deploy ポリシー**（共通）/ **bootstrap ポリシー**（手元だけ） | 手元から1回 |
| `roles.yaml` | ECS タスクが引く2つのロール | 手元から1回 |
| `db.yaml` | アプリの PostgreSQL（pgvector） | 手元から1回 |
| `waf.yaml` | CloudFront 用の WAF。**us-east-1** | CI |
| `ecr.yaml` | バックエンドのイメージ置き場 | CI |
| `app.yaml` | S3 / CloudFront / ALB / ECS Fargate / オートスケーリング / ログ | CI |

アカウント ID・VPC ID・サブネット ID はリポジトリに置かない。テンプレートは
`${AWS::AccountId}` などの擬似パラメータを使い、残りは GitHub Secrets から渡す。

## 権限の考え方

権限の定義は **`iam.yaml` の1箇所だけ**。CI のロールと手元の IAM ユーザーが同じ管理ポリシーを参照する。
変更したいときは `iam.yaml` を編集して流し直すだけで、両方に反映される。**JSON を手で貼る作業は無い。**

| ポリシー | 何ができるか | 誰に付くか |
| --- | --- | --- |
| `prtimes-hackathon-deploy` | スタック更新 / ECR / S3 / CloudFront / ECS / SG / WAF | CI（自動）＋ 手元 |
| `prtimes-hackathon-bootstrap` | ロール作成 / OIDC プロバイダ / **RDS** / SSM 書き込み | **手元だけ** |

**CI はロールを作れない。** `iam:CreateRole` を持たないので、権限の広いロールを作って ECS に渡す経路が無い。
タスクのロールは `roles.yaml` で一度だけ作り、CI は `iam:PassRole` で実名2本を渡すだけ。

**CI は RDS を触れない。** DB の作り直しがデプロイのたびに起きてよいことではないため。

主催者の資源（スタック・RDS・EC2）には **Deny** を置いてある。Deny は Allow に優先する。

## 初回だけやること

すべてリポジトリのルートで実行する。

```bash
cd "$(git rev-parse --show-toplevel)"
```

### 1. IAM 一式を作る

初回は手元のユーザーに十分な権限が要る。コンソールで一時的に強い権限を付けるか、管理者のセッションで実行する。

```bash
aws cloudformation deploy --profile prtimes --region ap-northeast-1 \
  --template-file infra/iam.yaml --stack-name prtimes-hackathon-oidc \
  --capabilities CAPABILITY_NAMED_IAM
```

同じアカウントに GitHub の OIDC プロバイダが既にあると `EntityAlreadyExists` で落ちる。

```bash
aws iam list-open-id-connect-providers --profile prtimes
aws cloudformation deploy ... --parameter-overrides CreateProvider=false ExistingProviderArn=<ARN>
```

できた2つの管理ポリシーを、IAM → ユーザー `prtimes-hackathon-deployer` →
許可を追加 → ポリシーを直接アタッチする、で付ける。**これ以降この作業は要らない。**

### 2. 秘密を Parameter Store に置く

値をシェル履歴に残さないよう対話で読む。

```bash
read -rs OPENAI_KEY
aws ssm put-parameter --profile prtimes --region ap-northeast-1 \
  --name /prtimes-hackathon/openai-api-key --type SecureString --value "$OPENAI_KEY" --overwrite
unset OPENAI_KEY

# CloudFront が ALB へ付ける秘密のヘッダ。これが無いリクエストを ALB は 403 で落とす
aws ssm put-parameter --profile prtimes --region ap-northeast-1 \
  --name /prtimes-hackathon/origin-verify --type SecureString --overwrite \
  --value "$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48)"
```

### 3. タスクのロールを作る

```bash
aws cloudformation deploy --profile prtimes --region ap-northeast-1 \
  --template-file infra/roles.yaml --stack-name prtimes-hackathon-roles \
  --capabilities CAPABILITY_NAMED_IAM
```

### 4. DB を作ってコーパスを入れる

パスワードは英数字だけで作る（RDS は `/ " @ 空白` を受け付けない）。

```bash
PW=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
aws ssm put-parameter --profile prtimes --region ap-northeast-1 \
  --name /prtimes-hackathon/db-password --type SecureString --value "$PW" --overwrite

aws cloudformation deploy --profile prtimes --region ap-northeast-1 \
  --template-file infra/db.yaml --stack-name prtimes-hackathon-db \
  --parameter-overrides VpcId=<vpc> PrivateSubnetIdA=<subnet> PrivateSubnetIdC=<subnet> \
    BastionSecurityGroupId=<sg> MasterUserPassword="$PW"

EP=$(aws cloudformation describe-stacks --profile prtimes --region ap-northeast-1 \
  --stack-name prtimes-hackathon-db \
  --query 'Stacks[0].Outputs[?OutputKey==`Endpoint`].OutputValue' --output text)
aws ssm put-parameter --profile prtimes --region ap-northeast-1 \
  --name /prtimes-hackathon/database-url --type SecureString --overwrite \
  --value "postgresql://prtimes:${PW}@${EP}:5432/app"
unset PW
```

RDS はプライベートサブネットにいるので、手元からは EC2 を踏み台にしたトンネルで入る。

```bash
ssh -i ~/.ssh/prtimes/hackathon.pem -N -f -o ServerAliveInterval=30 \
  -L "15434:$EP:5432" ubuntu@13.112.91.188

cd backend
uv run alembic upgrade head
uv run --group etl python -m etl.load_corpus
```

**これをやらないと `/api/proposal` がテーブル未作成で 500 になる。**

### 5. カレンダー連携を使うなら Google の値を置く（任意）

使わないなら飛ばしてよい。置かないうちは `/api/calendar/status` が `configured: false` を返し、
画面に連携の導線が出ないだけで、壁打ちも提案も動く。

Google Cloud Console で OAuth クライアント（種別: ウェブアプリケーション）を作り、
**承認済みのリダイレクト URI** に本番のものを登録する。

```
https://<CloudFront のドメイン>/api/calendar/oauth/callback
```

同意画面には `openid` / `userinfo.email` / `userinfo.profile` / `calendar.readonly` の4つを追加し、
公開ステータスがテストなら使う人をテストユーザーに入れる。Google Calendar API の有効化も要る。

得た2つを Parameter Store へ置く。**値は履歴に残さない。**

```bash
read -rs CID && aws ssm put-parameter --profile prtimes --region ap-northeast-1 \
  --name /prtimes-hackathon/google-client-id --type SecureString --overwrite --value "$CID"
read -rs CSEC && aws ssm put-parameter --profile prtimes --region ap-northeast-1 \
  --name /prtimes-hackathon/google-client-secret --type SecureString --overwrite --value "$CSEC"
unset CID CSEC
```

置くと**次のデプロイで自動的に有効になる**。CI がパラメータの有無を見て
`GoogleCalendarEnabled` を決めるので、手で切り替える必要はない。
リダイレクト URI と戻り先は CloudFront のドメインから組み立てられる。

### 5. GitHub に Secrets を3つ登録する

```bash
aws cloudformation describe-stacks --profile prtimes --region ap-northeast-1 \
  --stack-name prtimes-hackathon-oidc \
  --query 'Stacks[0].Outputs[?OutputKey==`DeployRoleArn`].OutputValue' --output text
aws ec2 describe-vpcs --profile prtimes --region ap-northeast-1 \
  --query 'Vpcs[?IsDefault==`false`].VpcId' --output text
aws ec2 describe-subnets --profile prtimes --region ap-northeast-1 \
  --filters Name=map-public-ip-on-launch,Values=true \
  --query 'Subnets[].[SubnetId,AvailabilityZone]' --output text
```

| 名前 | 例 |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::...:role/prtimes-hackathon-github-actions` |
| `VPC_ID` | `vpc-xxxxxxxx` |
| `PUBLIC_SUBNET_ID` | `subnet-aaaa`（既存のパブリック1枚。1c は app スタックが作る） |

## 以降のデプロイ

`main` に push すると [deploy.yml](../.github/workflows/deploy.yml) が動く。
手で回すなら Actions タブ → deploy → Run workflow。URL は実行サマリに出る。

**migration は CI が当てる。** サービスを入れ替える前に、本番と同じイメージを ECS の
使い捨てタスクとして VPC の中で起こして `alembic upgrade head` を流す。落ちたらそこで止まる。
コーパスの投入（`etl.load_corpus`）は自動では走らない。

## 止めるとき

```bash
aws cloudformation deploy --profile prtimes --region ap-northeast-1 \
  --template-file infra/app.yaml --stack-name prtimes-hackathon-app \
  --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset \
  --parameter-overrides MinTasks=0 MaxTasks=0 <他のパラメータも同じ値で>
```

全部消すときは app → waf → db → roles → ecr → iam の順。S3 は中身を空にしないと消えない。
`db.yaml` は `DeletionPolicy: Snapshot` なので、消してもスナップショットが残る。

## 詰まりやすいところ

| 症状 | 原因と直し方 |
| --- | --- |
| `UnauthorizedOperation` / `AccessDenied` | `iam.yaml` にアクションを足して流し直す。ポリシーの貼り直しは不要 |
| SG の作成が `Character sets beyond ASCII` で落ちる | `GroupDescription` に日本語は使えない。説明は YAML のコメントへ |
| List 型パラメータにカンマを渡せない | AWS CLI v1 の制約。パラメータを個別に分ける |
| ALB が 2 AZ 必要と言われる | `PUBLIC_SUBNET_ID` と新設する 1c が同じ AZ。`NewPublicSubnetAz` を変える |
| タスクが起動と停止を繰り返す | CloudWatch Logs `/ecs/...-backend`。秘密の取得失敗が多い |
| `/api/*` が 403 | ALB は `X-Origin-Verify` が一致しないと落とす。CloudFront 経由で叩いているか確認する |
| `CachePolicyId` が無いと言われる | `aws cloudfront list-cache-policies --type managed` で現行の ID に差し替える |
