# インフラ情報

秘密情報は含めない。パスワード・鍵は `.env` と鍵ファイル（どちらも git 管理外）に置く。

## AWS

| 項目 | 値 |
|---|---|
| アカウント | 622952748235 (`hackathon-2026-summer-team1`) |
| IAM ユーザー | `PRTIMES-Hackathon2026-Summer-Team1` / AdministratorAccess |
| リージョン | ap-northeast-1 |

## EC2

| 項目 | 値 |
|---|---|
| インスタンス | `i-0c72d1263ec5fef53` / t3.medium (2 vCPU / 4 GB) |
| Public IP | 13.112.91.188 |
| SG | `sg-03555db1c40d124bf` |
| OS | Ubuntu 24.04 と推定（OpenSSH 9.6p1 Ubuntu-3ubuntu13.18） |
| ログインユーザー | `ubuntu` |

### ポート使用状況

| ポート | 用途 |
|---|---|
| 22 | SSH |
| 80 | **pgAdmin 4（gunicorn）が使用中。潰さない** |
| 8080 | 空き → 本アプリを載せる |

## RDS

| 項目 | 値 |
|---|---|
| インスタンス | `prtimes-hackathon-2026summer-db` |
| エンドポイント | `prtimes-hackathon-2026summer-db.cnum2840eavk.ap-northeast-1.rds.amazonaws.com:5432` |
| SG | `sg-081829ee647a0df64` |
| **PubliclyAccessible** | **false** → ノートPCから直接繋がらない。EC2 経由が必須 |
| DB / ユーザー | `prtimes` / `hackathon` |

## アクセス方法

### SSH

```bash
chmod 600 <key.pem>
ssh -i <key.pem> ubuntu@13.112.91.188
```

### RDS へ（SSH トンネル経由）

```bash
# ターミナル1
ssh -i <key.pem> -N \
  -L 15432:prtimes-hackathon-2026summer-db.cnum2840eavk.ap-northeast-1.rds.amazonaws.com:5432 \
  ubuntu@13.112.91.188

# ターミナル2: localhost:15432 が RDS になる
docker run --rm -e PGPASSWORD="$DB_PASSWORD" postgres:16 \
  psql -h host.docker.internal -p 15432 -U hackathon -d prtimes -c '\dt+'
```

## セキュリティグループの操作

会場外から作業するために自宅 IP を追加済み。**IP が変わったら再登録が必要**（`curl -4 -s ifconfig.me` で確認）。

| ルールID | ポート | CIDR |
|---|---|---|
| `sgr-0220c775727dc7c57` | 22 | 49.109.140.15/32 |
| `sgr-0ff8c5eeb75678e6e` | 80 | 49.109.140.15/32 |
| `sgr-0c3fa947021494f01` | 8080 | 49.109.140.15/32 |

元から許可されていた IP: `125.103.31.194/32`, `147.192.56.66/32`（会場ネットワークと推定）

```bash
# 追加
aws ec2 authorize-security-group-ingress --region ap-northeast-1 \
  --group-id sg-03555db1c40d124bf --protocol tcp --port <PORT> --cidr <IP>/32

# 削除（ハッカソン終了後に自宅IPを閉じる）
aws ec2 revoke-security-group-ingress --region ap-northeast-1 \
  --group-id sg-03555db1c40d124bf --protocol tcp --port <PORT> --cidr <IP>/32
```

### 外部に公開する場合（デモ用）

```bash
aws ec2 authorize-security-group-ingress --region ap-northeast-1 \
  --group-id sg-03555db1c40d124bf --protocol tcp --port 8080 --cidr 0.0.0.0/0
```

22 番は絶対に `0.0.0.0/0` で開けない。

## チーム内で決めること

- ポート割り当て（80 = pgAdmin。8080 は本アプリが使用）
- EC2 上の作業ディレクトリ（`/home/ubuntu/<name>/`）
- systemd unit 名 / docker compose project 名の衝突回避
- RDS に書き込む場合はスキーマを分ける（`CREATE SCHEMA app_<name>`）

## 終了時のクリーンアップ

- [ ] SG から自宅 IP のルールを削除
- [ ] アクセスキーを作成した場合は IAM から削除
- [ ] 外部公開した 8080 の `0.0.0.0/0` を閉じる
