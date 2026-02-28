# aws-smoke-test

AWS 環境への自動デプロイを行うモノレポ。

## 構成

```
.github/workflows/
  aws-smoke-test.yml      # OIDC 認証の疎通確認
  deploy-notepad.yml      # メモ帳アプリのデプロイ
apps/notepad/              # React + TypeScript + Vite メモ帳アプリ
infrastructure/
  notepad-stack.yml        # CloudFormation テンプレート (S3 + CloudFront)
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

### 3. デプロイ

`main` ブランチに push すると自動デプロイされる（`apps/notepad/**` または `infrastructure/notepad-stack.yml` の変更時）。

手動実行: Actions > deploy-notepad > Run workflow
