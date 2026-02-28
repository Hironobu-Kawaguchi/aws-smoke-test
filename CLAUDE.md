# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS自動デプロイ用モノレポ。GitHub Actions (OIDC認証) 経由で CloudFormation + S3/CloudFront にデプロイする。ローカルからのAWSデプロイは行わない。

## Build & Development Commands

```bash
# Notepad app
cd apps/notepad
npm install          # Install dependencies
npm run dev          # Start dev server
npm run build        # Type check (tsc -b) + Vite build
npm run lint         # ESLint

# Chat app - Frontend
cd apps/chat/frontend
npm install          # Install dependencies
npm run dev          # Start dev server (proxy /api → localhost:8000)
npm run build        # Type check (tsc -b) + Vite build
npm run lint         # ESLint

# Chat app - Lambda (local dev)
cd apps/chat/lambda
uvicorn app:app --reload --port 8000
```

## Architecture

```
apps/                    # アプリケーション群（モノレポ）
  notepad/               # React 19 + TypeScript + Vite メモ帳アプリ (localStorage永続化)
  chat/
    lambda/              # FastAPI + Mangum Lambda バックエンド (OpenAI API + LangChain/LangSmith)
    frontend/            # React 19 + TypeScript + Vite チャットUI
infrastructure/          # CloudFormation テンプレート + IAMポリシー
  notepad-stack.yml      # S3 + CloudFront OAC
  chat-stack.yml         # Lambda + Function URL + S3 + CloudFront 2オリジン構成
  deploy-role-policy.json # GitHub Actionsロール用IAMポリシー
.github/workflows/
  deploy-notepad.yml     # main push → CFnデプロイ → ビルド → S3 sync → CF無効化
  deploy-chat.yml        # main push → CFn → Lambda更新 → ビルド → S3 sync → CF無効化
  aws-smoke-test.yml     # OIDC認証の疎通確認（手動実行）
```

### Chat app のデータフロー

```
Browser → CloudFront → /api/* → Lambda Function URL (OAC認証) → OpenAI API
                    → /*     → S3 (React SPA)           → Amazon Bedrock (Claude)
                                    ↑
                    Lambda → SSM Parameter Store (APIキー取得、lru_cacheで1回のみ)
                           → LangSmith (トレース送信、オプショナル)
```

- FastAPI は `APIRouter(prefix="/api")` でルーティング。CloudFront が `/api/*` パスをそのまま Lambda に転送するため、prefix が必須
- POST/PUT リクエストはクライアント側で `x-amz-content-sha256` ヘッダー（SHA256ハッシュ）が必要（CloudFront OAC + Lambda Function URL の要件）
- Lambda Function URL の OAC には `lambda:InvokeFunctionUrl` と `lambda:InvokeFunction` の両方の Permission が必要
- **マルチプロバイダー対応**: OpenAI (Responses API) と Amazon Bedrock (Converse API via langchain-aws) をモデル選択で切替。Bedrock モデルは Web Search / previous_response_id 非対応

## Deployment

- `main` ブランチへの push で自動デプロイ（各アプリのパス変更時）
- GitHub Actions が CloudFormation スタックをデプロイし、ビルド成果物を S3 に sync、CloudFront キャッシュを無効化
- CloudFormation の Outputs はワークフロー内で動的に取得される
- GitHub Actions Variables: `DEPLOY_ROLE_ARN` にIAMロールARNを設定済み
- **Chat app**: SSM Parameter Store に事前設定が必要:
  - `/chat-app/openai-api-key`（SecureString、必須）
  - `/chat-app/langsmith-api-key`（SecureString、オプショナル — 未設定時は LangSmith トレーシング無効）
- **Bedrock モデルアクセス**: AWS コンソール > Bedrock > Model access で以下を有効化:
  - Claude Opus 4.6, Claude Sonnet 4.6, Claude Haiku 4.5
- `deploy-role-policy.json` を変更した場合、IAMロールへの手動反映が別途必要（`aws iam put-role-policy` で更新）

## AWS Configuration

- **リージョン**: ap-northeast-1
- **認証**: GitHub Actions OIDC → `github-actions-smoke-test-role`
- **インフラ管理**: CloudFormation YAML（CDKは使わない）
- **CloudFront**: OAC (Origin Access Control) でS3/Lambdaアクセス。OAIは使わない
- **CloudFront CustomErrorResponses**: 403/404 を index.html に変換（SPA対応）。分配レベルで適用されるため、Lambda origin のエラーも変換される点に注意

## Linting

```bash
# Python (ruff)
uvx ruff check apps/chat/lambda/
uvx ruff format --check apps/chat/lambda/

# TypeScript (ESLint + tsc)
cd apps/notepad && npm run lint && npx tsc -b
cd apps/chat/frontend && npm run lint && npx tsc -b
```

- CI ワークフロー `.github/workflows/lint.yml` が PR/push 時に全リント・型チェックを実行
- Python 依存: `requirements.in`（非固定）→ `uv pip compile` → `requirements.txt`（固定）

## Observability

### ログ

- Lambda JSON 構造化ログ（`LoggingConfig` で自動変換、aws-lambda-powertools 不要）
- Log Group: `/aws/lambda/chat-stack-api`（14日保持）
- アプリケーションログに OpenAI API レイテンシ・トークン使用量を記録

### トレース

- **X-Ray**: Active トレース（Lambda 自動セグメント生成、コード変更不要）。AWS Console > X-Ray > Traces で確認
- **LangSmith**: LangChain Runnable 経由で OpenAI 呼び出しをトレース。SSM `/chat-app/langsmith-api-key` 設定時のみ有効。プロジェクト名: `aws-smoke-test`

### アラーム

- `chat-stack-lambda-errors`: Lambda エラー > 0 が3分連続で発火
- `chat-stack-lambda-duration-p90`: p90 レイテンシ > 20s で発火
- 通知先: SNS Topic `chat-stack-alarms`

### SNS 通知購読

```bash
aws sns subscribe \
  --topic-arn <AlarmTopicArn from stack outputs> \
  --protocol email \
  --notification-endpoint your@email.com
```

### CloudWatch Logs Insights クエリ

```
# エラー検索
fields @timestamp, @message | filter level = "ERROR" | sort @timestamp desc | limit 20

# OpenAI API レイテンシ
fields @timestamp, openai_duration_ms, model, usage_prompt_tokens, usage_completion_tokens
| filter openai_duration_ms > 0
| sort @timestamp desc | limit 50

# コールドスタート検出
filter @type = "REPORT" | fields @duration, @initDuration
| filter ispresent(@initDuration)
| sort @timestamp desc | limit 20
```

## Conventions

- 回答は日本語で生成する
- 新しいアプリは `apps/` 配下に追加する
- インフラテンプレートは `infrastructure/` 配下に配置する
- GitHub Actions ワークフローの `run:` で `${{ }}` を直接使わず、`env:` 経由で渡す（インジェクション対策）
- 新アプリ追加時は `deploy-role-policy.json` にスタック名パターンの権限を追加する
