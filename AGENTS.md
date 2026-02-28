# Repository Guidelines

## Project Structure & Module Organization
This repository is a small monorepo for AWS deployment smoke tests and sample web apps.
- `apps/notepad/`: React + TypeScript + Vite notepad frontend.
- `apps/notepad/src/`: Notepad UI code (`App.tsx`, `main.tsx`, CSS).
- `apps/chat/frontend/`: React + TypeScript + Vite chat frontend.
- `apps/chat/lambda/`: FastAPI + Mangum Lambda backend.
- `infrastructure/`: deployment artifacts (`notepad-stack.yml`, `chat-stack.yml`, `deploy-role-policy.json`).
- `.github/workflows/`: CI/CD workflows (`aws-smoke-test.yml`, `deploy-notepad.yml`, `deploy-chat.yml`).

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

Infrastructure deploy command (repo root):
- `aws cloudformation deploy --template-file infrastructure/notepad-stack.yml --stack-name notepad-stack --no-fail-on-empty-changeset`
- `aws cloudformation deploy --template-file infrastructure/chat-stack.yml --stack-name chat-stack --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset`

## Coding Style & Naming Conventions
Use TypeScript with 2-space indentation, single quotes, and no unnecessary semicolons to match existing files.
- React components: `PascalCase` (e.g., `NotepadPanel.tsx`).
- Functions/variables/hooks: `camelCase`.
- Constants: `UPPER_SNAKE_CASE` for module-level immutable values.

Linting is defined in each frontend app (`apps/notepad/eslint.config.js`, `apps/chat/frontend/eslint.config.js`); keep code lint-clean before pushing.

## Testing Guidelines
There is no dedicated unit-test framework configured yet. Current minimum quality gate is:
1. `cd apps/notepad && npm run lint && npm run build`
2. `cd apps/chat/frontend && npm run lint && npm run build`
3. Manual smoke tests:
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
Do not commit secrets or `.env*` files. Use GitHub Actions OIDC and repository variables (for example, `DEPLOY_ROLE_ARN`) for AWS authentication. For chat backend credentials, store the OpenAI key in SSM Parameter Store (`/chat-app/openai-api-key`) as `SecureString`.
