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
    lambda/              # FastAPI + Mangum Lambda バックエンド (OpenAI API)
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
                    → /*     → S3 (React SPA)
                                    ↑
                    Lambda → SSM Parameter Store (APIキー取得、lru_cacheで1回のみ)
```

- FastAPI は `APIRouter(prefix="/api")` でルーティング。CloudFront が `/api/*` パスをそのまま Lambda に転送するため、prefix が必須
- POST/PUT リクエストはクライアント側で `x-amz-content-sha256` ヘッダー（SHA256ハッシュ）が必要（CloudFront OAC + Lambda Function URL の要件）
- Lambda Function URL の OAC には `lambda:InvokeFunctionUrl` と `lambda:InvokeFunction` の両方の Permission が必要

## Deployment

- `main` ブランチへの push で自動デプロイ（各アプリのパス変更時）
- GitHub Actions が CloudFormation スタックをデプロイし、ビルド成果物を S3 に sync、CloudFront キャッシュを無効化
- CloudFormation の Outputs はワークフロー内で動的に取得される
- GitHub Actions Variables: `DEPLOY_ROLE_ARN` にIAMロールARNを設定済み
- **Chat app**: SSM Parameter Store に OpenAI API キーを事前設定が必要（`/chat-app/openai-api-key`、SecureString）
- `deploy-role-policy.json` を変更した場合、IAMロールへの手動反映が別途必要（`aws iam put-role-policy` で更新）

## AWS Configuration

- **リージョン**: ap-northeast-1
- **認証**: GitHub Actions OIDC → `github-actions-smoke-test-role`
- **インフラ管理**: CloudFormation YAML（CDKは使わない）
- **CloudFront**: OAC (Origin Access Control) でS3/Lambdaアクセス。OAIは使わない
- **CloudFront CustomErrorResponses**: 403/404 を index.html に変換（SPA対応）。分配レベルで適用されるため、Lambda origin のエラーも変換される点に注意

## Conventions

- 回答は日本語で生成する
- 新しいアプリは `apps/` 配下に追加する
- インフラテンプレートは `infrastructure/` 配下に配置する
- GitHub Actions ワークフローの `run:` で `${{ }}` を直接使わず、`env:` 経由で渡す（インジェクション対策）
- 新アプリ追加時は `deploy-role-policy.json` にスタック名パターンの権限を追加する
