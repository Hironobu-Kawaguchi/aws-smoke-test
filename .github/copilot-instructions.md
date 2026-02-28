# Copilot Instructions

## Project Overview

AWS自動デプロイ用モノレポ。GitHub Actions (OIDC認証) 経由で CloudFormation + S3/CloudFront にデプロイする。ローカルからのAWSデプロイは行わない。

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

アプリコードは `apps/<app-name>/src` に、インフラ変更は `infrastructure/` に配置する。1つのPRで両方を混ぜない。

## Build & Development Commands

```bash
# Notepad app
cd apps/notepad
npm ci               # ロックファイルからインストール
npm run dev          # Vite dev server 起動
npm run build        # TypeScript チェック (tsc -b) + Vite ビルド
npm run lint         # ESLint
npm run preview      # プロダクションビルドをローカル配信

# Chat app - Frontend
cd apps/chat/frontend
npm ci
npm run dev          # dev server (proxy /api → localhost:8000)
npm run build        # tsc -b + Vite ビルド
npm run lint

# Chat app - Lambda (ローカル開発)
cd apps/chat/lambda
uvicorn app:app --reload --port 8000
```

## Coding Style

- **TypeScript**: 2スペースインデント、シングルクォート、不要なセミコロンは省略
- **React コンポーネント**: `PascalCase` (例: `NotepadPanel.tsx`)
- **関数・変数・hooks**: `camelCase`
- **定数**: `UPPER_SNAKE_CASE` (モジュールレベルの不変値)
- **Python (Lambda)**: 標準的な PEP 8 スタイル
- リンティングは各アプリの `eslint.config.js` で定義。push 前に lint-clean にすること

## Testing

現時点で専用テストフレームワークは未導入。最低限の品質ゲート:

1. `npm run lint`
2. `npm run build`
3. `npm run dev` での手動スモークテスト

テストを追加する場合は `src/` 配下に `*.test.ts` / `*.test.tsx` で配置する。

## Commit & PR Conventions

- コミットメッセージは短く命令形で記述 (例: `Add notepad app with S3/CloudFront infrastructure`)
- コミットは焦点を絞りアトミックに
- タイトルは動詞で始める (`Add`, `Fix`, `Update`, `Replace`)

PRには以下を含める:
1. 目的とスコープ
2. 関連 issue/spec へのリンク
3. 実行した検証手順 (`lint`, `build`, 手動確認)
4. UI変更にはスクリーンショット、インフラ変更にはデプロイメモ

## AWS & Infrastructure

- **リージョン**: ap-northeast-1
- **認証**: GitHub Actions OIDC → `github-actions-smoke-test-role`
- **インフラ管理**: CloudFormation YAML（CDKは使わない）
- **CloudFront**: OAC (Origin Access Control) で S3/Lambda にアクセス。OAI は使わない
- シークレットや `.env*` ファイルはコミットしない
- GitHub Actions ワークフローの `run:` で `${{ }}` を直接使わず、`env:` 経由で渡す（インジェクション対策）

## Adding New Apps

- 新しいアプリは `apps/` 配下に追加する
- インフラテンプレートは `infrastructure/` 配下に配置する
- 新アプリ追加時は `deploy-role-policy.json` にスタック名パターンの権限を追加する

## Language

- 回答は日本語で生成する
