# Документация проекта Yuzu

Единая точка входа в документацию репозитория.

## Структура `docs/`

```text
docs/
├── README.md                  # Карта документации (этот файл)
├── architecture/              # Живая архитектура, контракты и RFC-спеки
│   ├── SYSTEM_OVERVIEW.md     # Контейнеры, сети, БД/Redis и схема конфигурации
│   ├── BACKEND_LAYERS.md      # Слои backend, границы зависимостей и import-linter
│   ├── CONTRACTS.md           # Инварианты API, валют, статусов и кодов дефектов
│   ├── openapi.json           # Автогенерируемый снимок OpenAPI из Django Ninja
│   └── specs/                 # Короткие 1-страничные RFC/ADR для новых фич
├── product/                   # Актуальная продуктовая и UI-документация
│   ├── PRODUCT_SPECIFICATION.md
│   ├── DESIGN.md
│   ├── BENCHMARK_CASE_COROLLA_TOURING.md
│   ├── showcase.html / showcase.png
│   ├── UX_COMPETITOR_RESEARCH.md
│   ├── LOCAL_DESIGN_PATTERNS_REPORT.md
│   └── WEB_LAYOUT_PRINCIPLES_REPORT.md
├── assets/                    # Брендинг, маскот Капибара Юдзу, wireframes
└── archive/                   # Исторические planning/, research/, domains/, старые контракты
```

## Быстрые ссылки

- **Система и деплой:** [architecture/SYSTEM_OVERVIEW.md](./architecture/SYSTEM_OVERVIEW.md)
- **Слои backend:** [architecture/BACKEND_LAYERS.md](./architecture/BACKEND_LAYERS.md)
- **Инварианты контрактов:** [architecture/CONTRACTS.md](./architecture/CONTRACTS.md) (машинный SSOT: [openapi.json](./architecture/openapi.json) → `frontend/src/types/api.generated.ts`)
- **Спецификация новых фич:** [architecture/specs/README.md](./architecture/specs/README.md)
- **Продукт и дизайн:** [product/PRODUCT_SPECIFICATION.md](./product/PRODUCT_SPECIFICATION.md), [product/DESIGN.md](./product/DESIGN.md), [product/showcase.html](./product/showcase.html)
- **Архив хакатона и R&D:** [archive/planning/README.md](./archive/planning/README.md), [archive/research/README.md](./archive/research/README.md)
