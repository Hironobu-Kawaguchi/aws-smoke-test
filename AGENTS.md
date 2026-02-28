# Repository Guidelines

## Project Structure & Module Organization
This repository is a small monorepo for AWS deployment smoke tests and a sample web app.
- `apps/notepad/`: React + TypeScript + Vite frontend.
- `apps/notepad/src/`: UI code (`App.tsx`, `main.tsx`, CSS).
- `infrastructure/`: deployment artifacts (`notepad-stack.yml`, IAM policy JSON).
- `.github/workflows/`: CI/CD workflows (`aws-smoke-test.yml`, `deploy-notepad.yml`).

Keep app code in `apps/notepad/src` and infrastructure changes in `infrastructure/`. Avoid mixing concerns in one PR.

## Build, Test, and Development Commands
Run commands from `apps/notepad` unless noted.
- `npm ci`: install locked dependencies.
- `npm run dev`: start local Vite dev server.
- `npm run build`: run TypeScript project build and produce production bundle.
- `npm run lint`: run ESLint on TypeScript/React files.
- `npm run preview`: serve the production build locally.

Infrastructure deploy command (repo root):
- `aws cloudformation deploy --template-file infrastructure/notepad-stack.yml --stack-name notepad-stack --no-fail-on-empty-changeset`

## Coding Style & Naming Conventions
Use TypeScript with 2-space indentation, single quotes, and no unnecessary semicolons to match existing files.
- React components: `PascalCase` (e.g., `NotepadPanel.tsx`).
- Functions/variables/hooks: `camelCase`.
- Constants: `UPPER_SNAKE_CASE` for module-level immutable values.

Linting is defined in `apps/notepad/eslint.config.js`; keep code lint-clean before pushing.

## Testing Guidelines
There is no dedicated unit-test framework configured yet. Current minimum quality gate is:
1. `npm run lint`
2. `npm run build`
3. Manual smoke test in `npm run dev` (edit text, save button state, Cmd/Ctrl+S behavior, reload persistence).

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
Do not commit secrets or `.env*` files. Use GitHub Actions OIDC and repository variables (for example, `DEPLOY_ROLE_ARN`) for AWS authentication.
