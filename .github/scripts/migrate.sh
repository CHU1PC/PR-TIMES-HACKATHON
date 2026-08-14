#!/usr/bin/env bash
# 本番と同じイメージを ECS の使い捨てタスクとして VPC の中で起こし alembic を流す。
# RDS はプライベートサブネットにいるので GitHub のランナーからは直接届かない。
# 要 env: APP_STACK / MIGRATE_FAMILY / IMAGE
set -euo pipefail

out() {
  aws cloudformation describe-stacks --stack-name "$APP_STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text 2>/dev/null
}

if ! current=$(aws ecs describe-task-definition --task-definition "$MIGRATE_FAMILY" \
  --query 'taskDefinition' --output json 2>/dev/null); then
  echo "初回デプロイ。スキーマは infra/README.md の手順で当てる"
  exit 0
fi

# 形は app.yaml が持つ。ここで差し替えるのは今積んだイメージだけ
spec=$(printf '%s' "$current" | python3 -c '
import json, os, sys

spec = json.load(sys.stdin)
for key in ("taskDefinitionArn", "revision", "status", "requiresAttributes",
            "compatibilities", "registeredAt", "registeredBy", "deregisteredAt"):
    spec.pop(key, None)
spec["containerDefinitions"][0]["image"] = os.environ["IMAGE"]
print(json.dumps(spec))
')

task_def=$(aws ecs register-task-definition --cli-input-json "$spec" \
  --query 'taskDefinition.taskDefinitionArn' --output text)

cluster=$(out ClusterName)
task=$(aws ecs run-task \
  --cluster "$cluster" \
  --task-definition "$task_def" \
  --launch-type FARGATE \
  --network-configuration \
    "awsvpcConfiguration={subnets=[$(out TaskSubnetIds)],securityGroups=[$(out TaskSecurityGroupId)],assignPublicIp=ENABLED}" \
  --query 'tasks[0].taskArn' --output text)

if [ -z "$task" ] || [ "$task" = "None" ]; then
  echo "::error::マイグレーションタスクを起動できなかった(配置失敗)"
  exit 1
fi
aws ecs wait tasks-stopped --cluster "$cluster" --tasks "$task"

# CLI v1 には logs tail が無い。失敗の判定はこの下の終了コードで行う
aws logs tail "$(out LogGroupName)" --since 15m \
  --log-stream-name-prefix "migrate/migrate/${task##*/}" || true

code=$(aws ecs describe-tasks --cluster "$cluster" --tasks "$task" \
  --query 'tasks[0].containers[0].exitCode' --output text)
if [ "$code" != "0" ]; then
  echo "::error::alembic upgrade head が終了コード $code で落ちた。新しいコードは載せない"
  exit 1
fi
