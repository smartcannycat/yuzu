# Agent Guidelines

## 1. General Rules

- Language: English only for all code, comments, documentation, and commit messages.
- No Emojis: Never use emojis in code, comments, commit messages, or documentation.

## 2. Package Manager

- Strictly use Bun (`bun`). Do not use npm, yarn, or pnpm.
- Never generate or commit foreign lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`).

## 3. Tooling & Quality

- Linter: `oxlint` (`bun run lint`, `bun run lint:fix`). Do not add ESLint.
- Formatter: `oxfmt` (`bun run format`, `bun run format:check`). Do not add Prettier.
- Type Checker: `vue-tsc` (`bun run typecheck`).
- Git Hooks: Managed by `lefthook` (runs oxlint, oxfmt, and typecheck on pre-commit).

## 4. Vue & TypeScript Standards

- SFC: Use Single File Components with `<script setup lang="ts">`.
- Strict Typing: Do not use `any`.
- Imports: Always use the `@/` path alias for imports from `src/`.
- Naming: `PascalCase.vue` for components, `useCamelCase.ts` for composables.

## 5. Styling, State & Routing

- Tailwind CSS v4: Zero-config via `@tailwindcss/vite` and `@import "tailwindcss";`. Never create `tailwind.config.js` or `postcss.config.js`.
- Pinia: Use setup store syntax (`defineStore('name', () => { ... })`).
- Vue Router: Use dynamic imports for views (`component: () => import('@/views/...')`).

## 6. Verification Checklist

Run and ensure passing status before completing any task:

1. `bun run typecheck`
2. `bun run lint`
3. `bun run format:check`
4. `bun run build`
