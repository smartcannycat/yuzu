# Спецификация миграции: Stageshow (Vue 3 + Bun + TypeScript)

> [!IMPORTANT]
> Цель: создание точной, высококачественной адаптации скилла `stageshow` под **Vue 3** (Composition API, `<script setup lang="ts">`, строгая типизация TypeScript) и рантайм/пакетный менеджер **Bun**, с сохранением всех визуальных стандартов, точной кинематики и вспомогательных утилит.

---

## 1. Локации и структура

| Назначение | Путь | Статус |
| :--- | :--- | :--- |
| **Оригинальный скилл (React)** | [.agents/skills/stageshow/](file:///home/weer/Documents/demos/.agents/skills/stageshow/) | Сохранён без изменений |
| **Портируемый скилл (Vue + Bun + TS)** | [.agents/skills/stageshow-vue/](file:///home/weer/Documents/demos/.agents/skills/stageshow-vue/) | Рабочая директория |

---

## 2. Стек технологий и окружение

* **Пакетный менеджер / Runtime**: `bun` (`bun install`, `bun run dev`, `bun.lock`).
* **Фреймворк**: Vue 3.5+ (строгий TypeScript, Composition API, `<script setup lang="ts">`, reactive/ref, provide/inject).
* **Иконки**: `lucide-vue-next`.
* **Сборка**: Vite с плагином `@vitejs/plugin-vue`.

### Зависимости (`package.json`)
* Удалены: `react`, `react-dom`, `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `lucide-react`.
* Установлены:
  * `vue`: `^3.5.0`
  * `lucide-vue-next`: `^0.468.0`
  * `@vitejs/plugin-vue`: `^5.0.0`
  * `typescript`: `^5.6.3`
  * `vue-tsc`: `^2.1.0`
  * `vite`: `^6.0.0`
  * `playwright-core`: `~1.48.2`

---

## 3. Матрица портирования модулей ядра (`kit/`)

Вся кодовая база строго на TypeScript (`.ts` и `.vue` с `<script setup lang="ts">`).

### 3.1. Движок сценариев и анимаций
1. **act.ts**:
   * Замена `flushSync` из `react-dom` на Vue `nextTick()`.
   * Адаптация механизма мутации состояния `set(patch)` и `put(patch)` под реактивную модель Vue (`Ref` / `shallowRef` / `reactive`).
   * Сохранение всех методов кинематики: `move`, `click`, `drag`, `scroll`, `caret`, `type`, `stagger`, `snap`, `enter`.
2. **looks.ts** и **reduced-motion.ts**:
   * Замена React Context на Vue `provide` / `inject`.
   * `useLook()` и `useReducedMotion()` как типизированные Vue composables.
3. **Stage.vue** (`stage.ts` / `Stage.vue`):
   * Масштабирование сцены (`ResizeObserver`, автоскейлинг).
   * Поддержка слотов: `#default`, оверлеи курсоров и кейкапов.
   * Управление переключением лейаута (`wide` / `compact`) и циклами проигрывания (`loop`, `once`, `hover`).

### 3.2. Курсоры и интерактивные слои
* **Cursor.vue**, **Cursors.vue**: рендеринг SVG-курсоров (`arrow`, `hand`, `ibeam`, `crosshair`, `grab`) и анимаций ряби (`ripple`).
* **Keys.vue** (`Keycaps`): рендеринг всплывающих кейкапов горячих клавиш.

### 3.3. Каркасы и экраны (Frames)
* **window**: `Window.vue`, `Bar.vue`, `Text.vue`, `Prompt.vue`, `Caret.vue`.
* **phone**: `Phone.vue`, `LockScreen.vue`, `Notification.vue`.
* **messages**: `Thread.vue`, `Bubble.vue`, `Stamp.vue`, `Receipt.vue`.
* **ios**: виртуальная клавиатура iOS (`Keyboard.vue`).
* **code** & **chart**: подсветка кода и SVG-графики.

### 3.4. Компоненты UI и моушна
* **`kit/controls/`**: `Badge`, `Field`, `Segmented`, `Slot`, `Tabs`, `Toggle`.
* **`kit/parts/`**: `Avatar`, `BrandMark`, `Check`, `Chip`, `Facepile`, `Icon` (Lucide Vue), `Menu`, `Meter`, `Pin`, `Row`, `Spinner`, `Toast`, `Tooltip`.
* **`kit/motion/`**: `Camera`, `Collapse`, `Connector`, `Count`, `Expand`, `Fly`, `Follow`, `Popover`, `Roll`, `Scroll`, `States`, `Stream`, `Swap`.
* **`kit/brands/`**: `index.ts` и локальные SVG-ассеты.

---

## 4. Плейграунд и скрипты автоматизации

1. **playground/**:
   * `vite.config.ts` с `@vitejs/plugin-vue`.
   * `main.ts` с инициализацией Vue приложения (`createApp(Viewer).mount('#root')`).
   * Компоненты каталога и просмотра (`Viewer.vue`, `Preview.vue`).
2. **scripts/**:
   * Адаптация `dev.mjs`, `film.mjs`, `verification.mjs` для запуска под `bun`.

---

## 5. Документация скилла

1. **SKILL.md**:
   * Описание и правила адаптированы под Vue 3 (`<template>`, `<script setup lang="ts">`, slots).
   * Команды запуска и сборки переведены на `bun`.
2. **references/**:
   * `kit.md` и сопутствующие файлы обновлены с типами и примерами Vue 3.

---

## 6. План приёмки и верификации

1. Установка зависимостей через `bun install`.
2. Проверка типов TypeScript через `bun run typecheck`.
3. Успешная сборка через `bun run build`.
