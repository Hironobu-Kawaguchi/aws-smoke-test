# aws-smoke-test

AWS 環境への自動デプロイを行うモノレポ。  
現在は `notepad` と `chat` の 2 アプリを管理しています。

## 構成

```
.github/workflows/
  aws-smoke-test.yml      # OIDC 認証の疎通確認
  deploy-notepad.yml      # notepad のデプロイ (CFn + S3 + CloudFront)
  deploy-chat.yml         # chat のデプロイ (CFn + Lambda + S3 + CloudFront)
  lint.yml                # リント・型チェック (TypeScript + Python)
apps/notepad/             # React + TypeScript + Vite メモ帳アプリ
apps/chat/
  frontend/               # React + TypeScript + Vite チャット UI
  lambda/                 # FastAPI + Mangum Lambda API
infrastructure/
  notepad-stack.yml        # CloudFormation テンプレート (S3 + CloudFront)
  chat-stack.yml           # CloudFormation テンプレート (Lambda + S3 + CloudFront + Monitoring)
  deploy-role-policy.json  # GitHub Actions ロール用 IAM ポリシー
```

## セットアップ手順（初回のみ）

### 1. IAM ロールにポリシーを追加

AWS Console で GitHub Actions 用ロールに `infrastructure/deploy-role-policy.json` のポリシーをアタッチする。

既存の `github-actions-smoke-test-role` を使う場合、そのロールにインラインポリシーとして追加。
または、新しいロールを作成する場合は OIDC 信頼ポリシーも設定する。

### 2. GitHub リポジトリの Variables を設定

Settings > Secrets and variables > Actions > Variables に以下を追加：

| Variable | 値 |
|----------|---|
| `DEPLOY_ROLE_ARN` | GitHub Actions が assume するロールの ARN |

### 3. Chat 用 API キーを SSM に登録

`chat` バックエンドは SSM Parameter Store の以下を参照します。
- `/chat-app/openai-api-key`
- `/chat-app/langsmith-api-key`

```zsh
# OpenAI API key
aws ssm put-parameter \
  --name /chat-app/openai-api-key \
  --type SecureString \
  --value 'YOUR_OPENAI_API_KEY' \
  --overwrite \
  --region ap-northeast-1

# LangSmith API key
aws ssm put-parameter \
  --name /chat-app/langsmith-api-key \
  --type SecureString \
  --value 'YOUR_LANGSMITH_API_KEY' \
  --overwrite \
  --region ap-northeast-1
```

### 4. SNS アラーム通知の購読（任意）

デプロイ後、Lambda エラー・高レイテンシのメール通知を受け取る場合:

```zsh
# AlarmTopicArn を取得
aws cloudformation describe-stacks --stack-name chat-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`AlarmTopicArn`].OutputValue' --output text

# メール購読
aws sns subscribe \
  --topic-arn <上記の ARN> \
  --protocol email \
  --notification-endpoint your@email.com
```

確認メールが届くので「Confirm subscription」リンクをクリックする。

### 5. デプロイ

`main` ブランチに push すると、変更パスに応じて自動デプロイされます。
- `deploy-notepad.yml`: `apps/notepad/**` または `infrastructure/notepad-stack.yml` の変更時
- `deploy-chat.yml`: `apps/chat/**` または `infrastructure/chat-stack.yml` の変更時

手動実行:
- Actions > `deploy-notepad` > Run workflow
- Actions > `deploy-chat` > Run workflow

## ローカル開発

### notepad

```zsh
cd apps/notepad
npm ci
npm run dev
```

### chat frontend

```zsh
cd apps/chat/frontend
npm ci
npm run dev
```

`apps/chat/frontend/vite.config.ts` で `/api` は `http://localhost:8000` にプロキシされます。

### chat backend (任意)

```zsh
cd apps/chat/lambda
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install uvicorn
uvicorn app:app --reload --port 8000
```

ローカルで `/api/chat` を使う場合、AWS 認証情報と SSM パラメータ
`/chat-app/openai-api-key`, `/chat-app/langsmith-api-key` が必要です。

オーケストレーション実行方式は環境変数で切り替えできます（デフォルト: `direct`）。

```zsh
export CHAT_ORCHESTRATOR=direct   # or langgraph
```

### chat backend テスト (開発専用)

`pytest` は開発・CI 専用です。Lambda 本番デプロイの `requirements.txt` には含めません。

```zsh
cd apps/chat/lambda
uv pip install --python .venv/bin/python -r requirements.txt pytest boto3
.venv/bin/python -m pytest -q
```

## リンティング

PR / main push 時に CI (`.github/workflows/lint.yml`) が自動実行されます。ローカルで事前チェック:

```zsh
# TypeScript (各フロントエンド)
cd apps/notepad && npm run lint && npx tsc -b
cd apps/chat/frontend && npm run lint && npx tsc -b

# Python (ruff)
uvx ruff check apps/chat/lambda/
uvx ruff format --check apps/chat/lambda/
```

Python 依存の更新手順:

```zsh
# requirements.in を編集後
cd apps/chat/lambda
uv pip compile requirements.in -o requirements.txt
```

## モニタリング

Chat app の Lambda には以下のオブザーバビリティが設定されています:

- **構造化ログ**: JSON 形式（CloudWatch Logs、14日保持）
- **X-Ray トレース**: コールドスタート・SSM/OpenAI API レイテンシの可視化
- **LangSmith トレース**: LangChain Runnable と OpenAI 呼び出しトレースの可視化
- **CloudWatch Alarms**: Lambda エラー検出 / p90 レイテンシ超過 → SNS メール通知
