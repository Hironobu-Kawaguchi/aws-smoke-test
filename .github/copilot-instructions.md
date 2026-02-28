# Copilot Instructions

## Project Overview

AWS自動デプロイ用モノレポ。GitHub Actions (OIDC認証) 経由で CloudFormation + S3/CloudFront にデプロイする。ローカルからのAWSデプロイは行わない。

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
  lint.yml               # リント・型チェック (TypeScript + Python)
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

# Python リント
uvx ruff check apps/chat/lambda/
uvx ruff format --check apps/chat/lambda/

# Python 依存更新
cd apps/chat/lambda && uv pip compile requirements.in -o requirements.txt
```

## Coding Style

- **TypeScript**: 2スペースインデント、シングルクォート、不要なセミコロンは省略
- **React コンポーネント**: `PascalCase` (例: `NotepadPanel.tsx`)
- **関数・変数・hooks**: `camelCase`
- **定数**: `UPPER_SNAKE_CASE` (モジュールレベルの不変値)
- **Python (Lambda)**: ruff (`apps/chat/lambda/ruff.toml`) で E/F/I/UP/B/SIM ルール適用
- リンティングは各フロントエンドの `eslint.config.js` と Python の `ruff.toml` で定義。push 前に lint-clean にすること
- CI (`.github/workflows/lint.yml`) が PR/push 時に全チェックを自動実行

## Testing

現時点で専用テストフレームワークは未導入。最低限の品質ゲート:

1. `npm run lint` + `npm run build`（各フロントエンド）
2. `uvx ruff check` + `uvx ruff format --check`（Python）
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

## Observability

Chat app Lambda のモニタリング構成（すべて AWS Free Tier 内）:
- **構造化ログ**: Lambda `LoggingConfig` による JSON 形式、14日保持。OpenAI API レイテンシ・トークン使用量を記録
- **X-Ray トレース**: Active モード（コード変更不要）
- **LangSmith トレース**: LangChain Runnable 経由で OpenAI 呼び出しをトレース。SSM `/chat-app/langsmith-api-key` 設定時のみ有効
- **CloudWatch Alarms**: Lambda エラー / p90 レイテンシ超過 → SNS メール通知
- **Python 依存管理**: `requirements.in`（非固定）→ `uv pip compile` → `requirements.txt`（固定）

## Language

- 回答は日本語で生成する
