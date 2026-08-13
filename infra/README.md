# インフラ

`docs/architecture.drawio` の構成を CloudFormation で作る。

| ファイル | 中身 | 誰が流すか |
| --- | --- | --- |
| `github-oidc.yaml` | GitHub Actions が引く IAM ロールと OIDC 信頼 | 手元から1回だけ |
| `ecr.yaml` | バックエンドのイメージ置き場 | CI（無ければ自動で作る） |
| `app.yaml` | S3 / CloudFront / ALB / ECS Fargate / ログ / ロール | CI |
| `deployer-policy.template.json` | 手元の IAM ユーザーに貼る権限。`ACCOUNT_ID` は置換して使う | 手動 |

アカウント ID・VPC ID・サブネット ID はリポジトリに置かない。テンプレートは
`${AWS::AccountId}` などの擬似パラメータを使い、残りは GitHub Secrets から渡す。

## 初回だけやること

以下のコマンドは**すべてリポジトリのルートで実行する**。`infra/` の中で叩くとパスが合わない。

```bash
cd "$(git rev-parse --show-toplevel)"
```

### 1. 手元の IAM ユーザーに権限を貼る

```bash
sed "s/ACCOUNT_ID/$(aws sts get-caller-identity --query Account --output text --profile prtimes)/g" \
  infra/deployer-policy.template.json | pbcopy
```

`sed` が失敗しても `pbcopy` は空を受け取ってクリップボードを消すだけで、エラーにならない。
貼る前に中身が入っているか確かめる。

```bash
pbpaste | python3 -c "import json,sys; print(len(json.load(sys.stdin)['Statement']), '件')"
```

貼り先は**インラインポリシーではなくカスタマー管理ポリシー**。空白を除いて 4,233 文字あり、
ユーザーのインラインポリシーの上限 2,048 文字に入らない（管理ポリシーは 6,144 文字）。

1. IAM → ポリシー → ポリシーを作成 → JSON タブに貼る → 名前 `prtimes-hackathon-deploy`
2. IAM → ユーザー `prtimes-hackathon-deployer` → 許可を追加 → ポリシーを直接アタッチする → 上で作ったものを選ぶ

| 貼り先 | 上限（空白を除いた文字数） |
| --- | --- |
| ユーザーのインラインポリシー | 2,048 |
| グループのインラインポリシー | 5,120 |
| カスタマー管理ポリシー | 6,144 |
| ロールのインラインポリシー | 10,240 |

IAM → ユーザー `prtimes-hackathon-deployer` → 許可を追加 → インラインポリシー → JSON に貼る。

### 2. OpenAI のキーを Parameter Store に置く

値をシェル履歴に残さないよう、対話で読む。

```bash
read -rs OPENAI_KEY
aws ssm put-parameter --profile prtimes --region ap-northeast-1 \
  --name /prtimes-hackathon/openai-api-key \
  --type SecureString --value "$OPENAI_KEY" --overwrite
unset OPENAI_KEY
```

### 3. GitHub Actions 用のロールを作る

```bash
aws cloudformation deploy --profile prtimes --region ap-northeast-1 \
  --template-file infra/github-oidc.yaml \
  --stack-name prtimes-hackathon-oidc \
  --capabilities CAPABILITY_NAMED_IAM
```

同じアカウントに GitHub の OIDC プロバイダが既にあると `EntityAlreadyExists` で落ちる。
そのときは既存の ARN を渡す。

```bash
aws iam list-open-id-connect-providers --profile prtimes
# ↑ で出た ARN を使って
aws cloudformation deploy --profile prtimes --region ap-northeast-1 \
  --template-file infra/github-oidc.yaml \
  --stack-name prtimes-hackathon-oidc \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides CreateProvider=false ExistingProviderArn=<ARN>
```

### 4. GitHub に Secrets を3つ登録する

値は次で引く。

```bash
# AWS_DEPLOY_ROLE_ARN
aws cloudformation describe-stacks --profile prtimes --region ap-northeast-1 \
  --stack-name prtimes-hackathon-oidc \
  --query 'Stacks[0].Outputs[?OutputKey==`DeployRoleArn`].OutputValue' --output text

# VPC_ID
aws ec2 describe-vpcs --profile prtimes --region ap-northeast-1 \
  --query 'Vpcs[?IsDefault==`false`].VpcId' --output text

# PUBLIC_SUBNET_IDS — AZ 違いで2つ。カンマ区切りで1つの値にする
aws ec2 describe-subnets --profile prtimes --region ap-northeast-1 \
  --filters Name=map-public-ip-on-launch,Values=true \
  --query 'Subnets[].[SubnetId,AvailabilityZone]' --output text
```

GitHub → Settings → Secrets and variables → Actions → New repository secret。

| 名前 | 例 |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::...:role/prtimes-hackathon-github-actions` |
| `VPC_ID` | `vpc-xxxxxxxx` |
| `PUBLIC_SUBNET_IDS` | `subnet-aaaa,subnet-bbbb` |

## 以降のデプロイ

`main` か `develop` に push すると `.github/workflows/deploy.yml` が動く。
手で回すなら Actions タブ → deploy → Run workflow。

やっていることは4つ。

1. イメージをビルドして ECR へ push（タグは git sha の先頭12桁）
2. `app.yaml` を流す。イメージのタグが変わるのでタスク定義が新しくなり、サービスが入れ替わる
3. フロントをビルドして S3 へ同期、CloudFront のキャッシュを飛ばす
4. `/api/health` が返るまで確かめる

URL は Actions の実行サマリに出る。

## 初回デプロイが通ったあとに権限を絞る

初期のポリシーは SG 系が `Resource: "*"` になっている。同じ VPC にいる既存の EC2 や
RDS の SG も理屈の上では触れる。作る前の SG は ID が無く名指しできないので、最初はこうするしかない。

一度デプロイが通ったら、**タグで絞る**形に差し替える。SG の ID を直書きしないので、
スタックを作り直しても壊れない。`app.yaml` は両方の SG に `Project=prtimes-hackathon` を
付けており、これが鍵になる（このタグを外すと権限エラーになる）。

絞る対象は2つある。**CI 側を絞らないと意味が薄い**（実際にデプロイするのは CI）。

### 1. ローカルの IAM ユーザー

```bash
cd "$(git rev-parse --show-toplevel)"
VPC=$(aws cloudformation describe-stacks --profile prtimes --region ap-northeast-1 \
  --stack-name prtimes-hackathon-app \
  --query 'Stacks[0].Parameters[?ParameterKey==`VpcId`].ParameterValue' --output text)
sed -e "s/ACCOUNT_ID/$(aws sts get-caller-identity --query Account --output text --profile prtimes)/g" \
    -e "s/VPC_ID/$VPC/g" \
  infra/deployer-policy-tight.template.json | pbcopy
```

IAM → ポリシー → `prtimes-hackathon-deployer` → 編集 → JSON を差し替えて保存。

### 2. CI が引くロール

`github-oidc.yaml` の `ManageOwnSecurityGroups` を丸ごと次の5文に置き換え、
`VpcId` パラメータを足してスタックを流し直す。

```yaml
              - Sid: CreateSecurityGroupsInThisVpcOnly
                Effect: Allow
                Action: ec2:CreateSecurityGroup
                Resource:
                  - !Sub "arn:aws:ec2:${AWS::Region}:${AWS::AccountId}:security-group/*"
                  - !Sub "arn:aws:ec2:${AWS::Region}:${AWS::AccountId}:vpc/${VpcId}"

              - Sid: TagSecurityGroupsOnlyWhileCreating
                Effect: Allow
                Action: ec2:CreateTags
                Resource: !Sub "arn:aws:ec2:${AWS::Region}:${AWS::AccountId}:security-group/*"
                Condition:
                  StringEquals:
                    ec2:CreateAction: CreateSecurityGroup

              - Sid: ChangeOnlyOurOwnSecurityGroups
                Effect: Allow
                Action:
                  - ec2:DeleteSecurityGroup
                  - ec2:AuthorizeSecurityGroupIngress
                  - ec2:AuthorizeSecurityGroupEgress
                  - ec2:RevokeSecurityGroupIngress
                  - ec2:RevokeSecurityGroupEgress
                  - ec2:ModifySecurityGroupRules
                  - ec2:DeleteTags
                Resource: !Sub "arn:aws:ec2:${AWS::Region}:${AWS::AccountId}:security-group/*"
                Condition:
                  StringEquals:
                    aws:ResourceTag/Project: prtimes-hackathon

              # ルールは SG とは別の資源として扱われる。これが無いと ModifySecurityGroupRules が落ちる
              - Sid: SecurityGroupRulesAreASeparateResource
                Effect: Allow
                Action: ec2:ModifySecurityGroupRules
                Resource: !Sub "arn:aws:ec2:${AWS::Region}:${AWS::AccountId}:security-group-rule/*"

              # プレフィックスリストは AWS 管理でタグを付けられないため資源指定できない
              - Sid: ReadCloudFrontPrefixList
                Effect: Allow
                Action: ec2:GetManagedPrefixListEntries
                Resource: "*"
```

### 3. 絞りすぎていないか確かめる

絞ったあとに**もう一度デプロイを流す**。ここで初めて権限が足りているとわかる。

```bash
gh workflow run deploy.yml --ref main && sleep 5 && gh run watch
```

`UnauthorizedOperation` が出たら絞りすぎ。エラーが名指しするアクションを見て、
資源指定を `"*"` に戻すか、条件を外す。

## 止めるとき

タスクの課金だけ止める。

```bash
aws cloudformation deploy --profile prtimes --region ap-northeast-1 \
  --template-file infra/app.yaml --stack-name prtimes-hackathon-app \
  --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset \
  --parameter-overrides DesiredCount=0 <他のパラメータも同じ値で>
```

全部消すときは app → ecr → oidc の順。S3 は中身を空にしないと消えない。

```bash
aws s3 rm "s3://$(aws cloudformation describe-stacks --stack-name prtimes-hackathon-app \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' --output text)" --recursive
aws cloudformation delete-stack --stack-name prtimes-hackathon-app
```

## 詰まりやすいところ

| 症状 | 原因と直し方 |
| --- | --- |
| `UnauthorizedOperation` / `AccessDenied` | 手順1のポリシーが貼られていない。エラーが名指しするアクションを足す |
| ALB が 2 AZ 必要と言われる | `PUBLIC_SUBNET_IDS` が同じ AZ の2つ。AZ 違いで選び直す |
| タスクが起動と停止を繰り返す | CloudWatch Logs の `/ecs/...-backend` を見る。キーの取得失敗が多い |
| ターゲットが unhealthy のまま | ヘルスチェックは `/api/health`。ルータの prefix を変えたら合わせる |
| `CachePolicyId` が無いと言われる | `aws cloudfront list-cache-policies --type managed` で現行の ID を確認して差し替える |
