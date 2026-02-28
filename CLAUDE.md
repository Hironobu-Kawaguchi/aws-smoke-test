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
npm run preview      # Preview built site

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
  notepad-stack.yml      # S3 + CloudFront OAC (デプロイはGitHub Actionsが実行)
  chat-stack.yml         # Lambda + Function URL + S3 + CloudFront 2オリジン構成
  deploy-role-policy.json # GitHub Actionsロール用IAMポリシー
.github/workflows/
  deploy-notepad.yml     # main push → CFnデプロイ → ビルド → S3 sync → CF無効化
  deploy-chat.yml        # main push → CFn → Lambda更新 → ビルド → S3 sync → CF無効化
  aws-smoke-test.yml     # OIDC認証の疎通確認（手動実行）
```

## Deployment

- `main` ブランチへの push で自動デプロイ（各アプリのパス変更時）
- GitHub Actions が CloudFormation スタックをデプロイし、ビルド成果物を S3 に sync、CloudFront キャッシュを無効化
- CloudFormation の Outputs はワークフロー内で動的に取得される
- GitHub Actions Variables: `DEPLOY_ROLE_ARN` にIAMロールARNを設定済み
- **Chat app**: SSM Parameter Store に OpenAI API キーを事前設定が必要（`/chat-app/openai-api-key`、SecureString）

## AWS Configuration

- **リージョン**: ap-northeast-1
- **認証**: GitHub Actions OIDC → `github-actions-smoke-test-role`
- **インフラ管理**: CloudFormation YAML（CDKは使わない）
- **CloudFront**: OAC (Origin Access Control) でS3アクセス。OAIは使わない

## Conventions

- 回答は日本語で生成する
- 新しいアプリは `apps/` 配下に追加する
- インフラテンプレートは `infrastructure/` 配下に配置する
- GitHub Actions ワークフローの `run:` で `${{ }}` を直接使わず、`env:` 経由で渡す（インジェクション対策）
