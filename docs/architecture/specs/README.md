# Feature Specifications & ADRs (`docs/architecture/specs/`)

Write a 1-page spec here **before** implementing significant features or cross-service contract changes.

## Naming

`NNN-short-kebab-title.md` (e.g. `001-manual-power-override.md`)

## Template

```markdown
# NNN: <Title>

- **Status:** Draft | Approved | Shipped
- **Services affected:** backend | ml_service | frontend

## Problem & Goal
Why this change is needed (3–5 sentences).

## Contract & Domain Invariants
- Exact API/schema additions or enum updates
- Edge cases, failure modes, and permission checks

## Verification Plan
- Unit/integration tests and contract sync (`make check-contracts`)
```
