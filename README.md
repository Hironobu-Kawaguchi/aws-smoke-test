# aws-smoke-test

AWS 環境への自動デプロイを行うモノレポ。  
現在は `notepad` と `chat` の 2 アプリを管理しています。

## 構成

```
.github/workflows/
  aws-smoke-test.yml      # OIDC 認証の疎通確認
  deploy-notepad.yml      # notepad のデプロイ (CFn + S3 + CloudFront)
  deploy-chat.yml         # chat のデプロイ (CFn + Lambda + S3 + CloudFront)
apps/notepad/             # React + TypeScript + Vite メモ帳アプリ
apps/chat/
  frontend/               # React + TypeScript + Vite チャット UI
  lambda/                 # FastAPI + Mangum Lambda API
infrastructure/
  notepad-stack.yml        # CloudFormation テンプレート (S3 + CloudFront)
  chat-stack.yml           # CloudFormation テンプレート (Lambda + S3 + CloudFront)
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

### 3. Chat 用 OpenAI API キーを SSM に登録

`chat` バックエンドは SSM Parameter Store の `/chat-app/openai-api-key` を参照します。

```zsh
aws ssm put-parameter \
  --name /chat-app/openai-api-key \
  --type SecureString \
  --value 'YOUR_OPENAI_API_KEY' \
  --overwrite \
  --region ap-northeast-1
```

### 4. デプロイ

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

ローカルで `/api/chat` を使う場合、AWS 認証情報と SSM パラメータ `/chat-app/openai-api-key` が必要です。
