# Repository Guidelines

## Project Structure & Module Organization
This repository is a small monorepo for AWS deployment smoke tests and sample web apps.
- `apps/notepad/`: React + TypeScript + Vite notepad frontend.
- `apps/notepad/src/`: Notepad UI code (`App.tsx`, `main.tsx`, CSS).
- `apps/chat/frontend/`: React + TypeScript + Vite chat frontend.
- `apps/chat/lambda/`: FastAPI + Mangum Lambda backend (OpenAI API + LangChain/LangSmith).
- `infrastructure/`: deployment artifacts (`notepad-stack.yml`, `chat-stack.yml`, `deploy-role-policy.json`).
- `.github/workflows/`: CI/CD workflows (`aws-smoke-test.yml`, `deploy-notepad.yml`, `deploy-chat.yml`, `lint.yml`).

Keep application code in each app directory and infrastructure changes in `infrastructure/`. Avoid mixing concerns in one PR.

## Build, Test, and Development Commands
Run commands from each app directory unless noted.
- `cd apps/notepad && npm ci`: install locked dependencies for notepad.
- `cd apps/notepad && npm run dev`: start local notepad dev server.
- `cd apps/notepad && npm run lint`: run ESLint for notepad.
- `cd apps/notepad && npm run build`: run TypeScript build and create notepad production bundle.
- `cd apps/chat/frontend && npm ci`: install locked dependencies for chat frontend.
- `cd apps/chat/frontend && npm run dev`: start local chat frontend dev server (proxies `/api` to `http://localhost:8000`).
- `cd apps/chat/frontend && npm run lint`: run ESLint for chat frontend.
- `cd apps/chat/frontend && npm run build`: run TypeScript build and create chat frontend production bundle.
- `uvx ruff check apps/chat/lambda/`: run ruff linter on Python Lambda code.
- `uvx ruff format --check apps/chat/lambda/`: check ruff formatting on Python Lambda code.
- `cd apps/chat/lambda && uv pip compile requirements.in -o requirements.txt`: regenerate pinned dependencies.

Infrastructure deploy command (repo root):
- `aws cloudformation deploy --template-file infrastructure/notepad-stack.yml --stack-name notepad-stack --no-fail-on-empty-changeset`
- `aws cloudformation deploy --template-file infrastructure/chat-stack.yml --stack-name chat-stack --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset`

## Coding Style & Naming Conventions
Use TypeScript with 2-space indentation, single quotes, and no unnecessary semicolons to match existing files.
- React components: `PascalCase` (e.g., `NotepadPanel.tsx`).
- Functions/variables/hooks: `camelCase`.
- Constants: `UPPER_SNAKE_CASE` for module-level immutable values.

Linting is defined in each frontend app (`apps/notepad/eslint.config.js`, `apps/chat/frontend/eslint.config.js`) and Python (`apps/chat/lambda/ruff.toml`); keep code lint-clean before pushing. CI runs all checks via `.github/workflows/lint.yml` on PR and push to main.

## Testing Guidelines
There is no dedicated unit-test framework configured yet. Current minimum quality gate is:
1. `cd apps/notepad && npm run lint && npm run build`
2. `cd apps/chat/frontend && npm run lint && npm run build`
3. `uvx ruff check apps/chat/lambda/ && uvx ruff format --check apps/chat/lambda/`
4. Manual smoke tests:
   - Notepad: edit text, save button state, Cmd/Ctrl+S behavior, reload persistence.
   - Chat frontend: send by button and Enter key, loading state, assistant/error message rendering.
   - Chat API: `/api/health` returns `{"status":"ok"}` after deployment (or local backend run).

When adding tests, colocate them under `src/` with `*.test.ts` or `*.test.tsx`.

## Commit & Pull Request Guidelines
Commit style in history is short, imperative, and descriptive (e.g., `Add notepad app with S3/CloudFront CDK infrastructure`).
- Keep commits focused and atomic.
- Start commit titles with a verb (`Add`, `Fix`, `Update`, `Replace`).

PRs should include:
1. Purpose and scope.
2. Linked issue/spec.
3. Validation steps run (`lint`, `build`, manual checks).
4. Screenshots for UI changes and deployment notes for infrastructure updates.

## Security & Configuration Tips
Do not commit secrets or `.env*` files. Use GitHub Actions OIDC and repository variables (for example, `DEPLOY_ROLE_ARN`) for AWS authentication. For chat backend credentials, store API keys in SSM Parameter Store as `SecureString`: `/chat-app/openai-api-key` (required) and `/chat-app/langsmith-api-key` (optional — LangSmith tracing is disabled when absent).

## Observability

Chat app Lambda has the following monitoring configured (all within AWS Free Tier):
- **Structured logging**: JSON format via Lambda `LoggingConfig`, 14-day retention. Application logs include OpenAI API latency (`openai_duration_ms`) and token usage.
- **X-Ray tracing**: Active mode, auto-generated segments for cold start and downstream calls.
- **LangSmith tracing**: OpenAI calls traced via LangChain Runnable. Enabled only when SSM `/chat-app/langsmith-api-key` is set. Project: `aws-smoke-test`.
- **CloudWatch Alarms**: Lambda errors (Sum > 0 for 3 consecutive minutes) and p90 duration (> 20s). Both notify via SNS topic `chat-stack-alarms`.
- **Python dependencies**: Pinned via `requirements.in` → `uv pip compile` → `requirements.txt`.
