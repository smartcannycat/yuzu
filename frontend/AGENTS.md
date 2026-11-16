# Frontend Agent Guidelines

## 1. General Rules

- Language: English only for code, comments, technical documentation, and commit messages. UI copy is Russian.
- No Emojis: Never use emojis in code, comments, commit messages, or technical docs.

## 2. Package Manager & Tooling

- Strictly use Bun (`bun`). Do not use npm, yarn, or pnpm, and never commit foreign lockfiles.
- Linter: `oxlint` (`bun run lint`). Formatter: `oxfmt` (`bun run format:check`). Type checker: `vue-tsc` (`bun run typecheck`).
- Git Hooks: managed at repository root by `lefthook.yml`.

## 3. API Contracts & Domain Enums

- Machine contract types live in `src/types/api.generated.ts`, generated from `../docs/architecture/openapi.json` via `bun run gen:api`. Keep them synced (`make check-contracts` at repo root) and never hand-edit `api.generated.ts` or run `oxfmt` on it.
- Always branch UI state on canonical backend enum fields (e.g., `PartSourceKind`, `TrafficLightColor`, `BatchStatus`, `ItemProcessingStatus`, `PowerHpSource`, `UtilFeeType`), **never** by substring-matching localized Russian UI strings.

## 4. Vue, TypeScript & Module Size Standards

- Soft module size limit: **~300–350 lines** per `.ts` or `.vue` file (excluding generated `api.generated.ts`). Extract composables, presenters, or subcomponents cleanly instead of growing god components.
- SFC: `<script setup lang="ts">`. Strict typing without `any`. Always use `@/` alias for `src/` imports.
- Tailwind CSS v4: `@tailwindcss/vite` + `@import "tailwindcss";`. Never add `tailwind.config.js` or `postcss.config.js`.
- Pinia: setup stores (`defineStore('name', () => { ... })`). Vue Router: lazy route views (`() => import('@/views/...')`).

## 5. Verification Checklist

Before completing any task, ensure all pass:

1. `bun run typecheck`
2. `bun run lint`
3. `bun run format:check`
4. `bun run check:api`
5. `bun run test` && `bun run build`
