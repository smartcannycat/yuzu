---
version: alpha
name: Clean Light
description: Прецизионная светлая дизайн-система высокой плотности на базе типографики SF Pro Display, тональной иерархии холста, вытянутого свитча iOS 26, бесшовных статус-капсул и иконографики Lucide Icons.
---

# YUZU Clean Light Design System

## Overview

Прецизионная дизайн-система сервиса сквозного анализа аукционных листов и расчета себестоимости автомобилей под ключ во Владивостоке — **YUZU** (_Интеллект японских автоаукционов_).

- **Бренд и дескриптор**: Официальное наименование продукта — **YUZU**. Для снятия абстрактности на всех титульных экранах и документах закрепляется обязательный институциональный дескриптор: `YUZU // Интеллект японских автоаукционов` (в отчетах: `YUZU Report: Экспертное заключение дефектоскопии и себестоимости`).
- **Маскот «Дзен-Инспектор»**: Капибара по имени **Юдзу** — спокойный, невозмутимый эксперт, снимающий тревогу покупателя. Она присутствует строго в 4 сценариях (Dropzone, сканирование 2с, карточка вердикта 🟢/🟡/🔴, ошибка фото), не загромождая финансовые таблицы.
- **Тональная светлая архитектура**: Отказ от слепящего белого фона в пользу ступенчатого контраста холста (`#F2F2F7`), чистых белых карточек (`#FFFFFF`) и волосяных разделителей (`#E5E5EA`).
- **Швейцарская типографика**: Полный перевод интерфейса на семейство шрифтов **SF Pro Display** без искусственной перегрузки жирностью (баланс 400 Regular, 500 Medium и 600 SemiBold).
- **Иконографика**: Официальный стандарт интерфейсных иконок — **Lucide Icons** (штрих 1.75–2px, `currentColor`, строгая цветовая привязка к тону текста).
- **Вытянутый свитч (iOS 26 Style)**: Инновационный переключатель с капсульным (вытянутым овальным) бегунком вместо круглого, двигающимся внутри капсульного трека.
- **Бесшовные статус-капсулы (Soft Tints)**: Бескаркасные пастельные капсулы с векторными иконками Lucide в цвет текста и нейтральный эталон (`#EFEFF4`) для технических параметров (по образцу «Бензин 1.8L»).
- **Дисциплина акцента (Правило 90/10)**: 90% элементов выдержаны в спокойном монохроме, а теплый фирменный цвет Farpost Orange (`#FF6B00`) зарезервирован исключительно под целевые действия, активный свитч и фокусные рамки.

## Colors

Цветовая палитра разделена на тональные фоновые уровни, нейтральный монохромный текст, единственный конверсионный акцент и мягкий бескаркасный светофор рисков.

- **Canvas Ground (`#F2F2F7`)**: Мягкий базовый фон экрана, снимающий зрительное напряжение и формирующий глубокий контраст для белых поверхностей.
- **Surface Cards (`#FFFFFF`)**: Чистый белый цвет группирующих контейнеров и карточек.
- **Surface Inset (`#EFEFF4`)**: Углубленный серый фон для полей ввода, сегментированных переключателей и нейтральных капсул ТТХ.
- **Borders & Dividers (`#E5E5EA`, `#D1D1D6`)**: Тонкие волосяные делители 0.5px и мягкие карточные контуры 1px.
- **Text Hierarchy (`#111827`, `#6B7280`, `#9CA3AF`)**: Глубокий угольный цвет основного чтения, нейтральный серый для метаданных и приглушенный для вспомогательных меток.
- **Conversion Accent (`#FF6B00`)**: Единственный акцентный цвет для Primary-кнопок, активного состояния свитча iOS 26, активных табов и фокуса.
- **Soft Seamless Status Colors (Без грубых рамок, иконка строго в цвет текста)**:
  - _Success (Низкий риск)_: Текст и иконка `#15803D`, мягкий фон `#F0FDF4`.
  - _Warning (Внимание)_: Текст и иконка `#B45309`, мягкий фон `#FFFBEB`.
  - _Danger (Стоп-фактор)_: Текст и иконка `#B91C1C`, мягкий фон `#FEF2F2`.
  - _Info (Служебный)_: Текст и иконка `#1D4ED8`, мягкий фон `#EFF6FF`.
  - _Neutral TTX Capsule_: Текст и иконка `#6B7280`, мягкий фон `#EFEFF4` (по образцу «Бензин 1.8L»).

```yaml
colors:
  primary: '#111827'
  secondary: '#6B7280'
  tertiary: '#FF6B00'
  tertiary-hover: '#E55F00'
  tertiary-active: '#CC5500'
  tertiary-subtle: '#FFF4ED'
  neutral: '#F2F2F7'
  surface: '#FFFFFF'
  surface-inset: '#EFEFF4'
  surface-hover: '#F8F8FA'
  border: '#E5E5EA'
  border-subtle: '#F2F2F7'
  border-focus: '#FF6B00'
  text-primary: '#111827'
  text-secondary: '#6B7280'
  text-muted: '#9CA3AF'
  text-on-accent: '#FFFFFF'
  success: '#15803D'
  success-bg: '#F0FDF4'
  warning: '#B45309'
  warning-bg: '#FFFBEB'
  danger: '#B91C1C'
  danger-bg: '#FEF2F2'
  info: '#1D4ED8'
  info-bg: '#EFF6FF'
```

## Typography

Типографическая шкала построена на семействе **SF Pro Display** с пропорциональными цифрами. Начертания распределены по строгой функциональной иерархии:

- **Regular (400)**: Чтение длинных текстов, описания дефектов, пояснения к расходам.
- **Medium (500)**: Кнопки, подписи контролов, заголовки параметров в сетке ТТХ, статус-капсулы.
- **SemiBold (600)**: Заголовки секций, цены лотов, модальные заголовки и итоговые сметы.

```yaml
typography:
  display-large:
    fontFamily: SF Pro Display
    fontSize: 34px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.02em
  title-1:
    fontFamily: SF Pro Display
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: -0.015em
  title-2:
    fontFamily: SF Pro Display
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.01em
  headline:
    fontFamily: SF Pro Display
    fontSize: 17px
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: SF Pro Display
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.45
  body-medium:
    fontFamily: SF Pro Display
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.45
  subhead:
    fontFamily: SF Pro Display
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
  input-text:
    fontFamily: SF Pro Display
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
  caption:
    fontFamily: SF Pro Display
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.35
  badge-label:
    fontFamily: SF Pro Display
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: 0.01em
```

## Layout

Сетка построена на кратности 8px (с микро-шагом 4px для плотных данных).

- **Колоночная структура**: Центральный контентный блок ограничен `max-width: 680px` на мобильных и `1200px` в многоколоночном десктоп-режиме.
- **Разделители вместо рамок**: Внутри карточек строки разделяются волосяными линиями 0.5px с отступом слева под текст (`margin-left: 16px` или `56px` при наличии иконки).

```yaml
spacing:
  '2xs': 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 24px
  '2xl': 32px
  '3xl': 48px
  card-padding: 16px
  input-height: 44px
  button-height: 44px
  switch-track-width: 52px
  switch-track-height: 26px
  switch-thumb-width: 28px
  switch-thumb-height: 22px
  bottom-bar-height: 60px
  max-width: 1200px
```

## Elevation & Depth

Легкая многослойная архитектура (Tonal Layering), имитирующая физическую бумагу и нативные слои iOS/Telegram:

- **Level 0 (Canvas Ground)**: Базовый серый фон `#F2F2F7`.
- **Level 1 (Surface Cards)**: Белые карточки `#FFFFFF` с тонким контуром `1px solid #E5E5EA`, статичной базовой микротенью `0 1px 2px rgba(0, 0, 0, 0.03)` и отсутствием размытых или усиливающихся теней при наведении.
- **Hover без теней (Color-Only Hover)**: 90% интерактивных поверхностей и карточек обозначают наведение исключительно спокойным изменением цвета (рамки, фона, заголовка или иконки), не меняя тень и не «всплывая» над холстом.
- **Level Inset**: Углубленные поля ввода и капсулы с подложкой `#EFEFF4`.
- **Switch Thumb**: Белый капсульный бегунок с деликатной физической тенью `0 2px 4px rgba(0, 0, 0, 0.15)`.

## Shapes

Геометрическая шкала со скруглениями:

```yaml
rounded:
  none: 0px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 20px
  full: 9999px
```

## Components

Спецификация базовых атомов и типовых интерфейсных узлов дизайн-системы с иконками Lucide Icons.

- **Switch iOS 26 (Вытянутый капсульный тоггл)**:
  - Трек: ширина `52px`, высота `26px`, скругление `9999px`. Цвет: неактивный `#E9E9EB`, активный `#FF6B00`.
  - Бегунок: вытянутая капсула `28×22px`, скругление `9999px`. Ход: от `left: 2px` до `right: 2px` (`translateX(20px)`).
- **Status Badges (Бесшовные тинты с Lucide иконками)**:
  - Формат: мягкий бескаркасный фон (без обводки 1px), высота 24px, паддинг 4px 10px, скругление `full`.
  - Векторная иконка Lucide 14px с `stroke: currentColor` строго наследует цвет текста капсулы.
- **Buttons**: Primary (акцентный оранжевый), Secondary (нейтральный серый), Ghost, Destructive.
- **List Rows & TTX Grids**: Строка списка с цветными сквирклами 28×28px и иконками Lucide, двухколоночная сетка характеристик без вертикальных рамок.

```yaml
components:
  switch-ios-26:
    width: '{spacing.switch-track-width}'
    height: '{spacing.switch-track-height}'
    backgroundColor: '{colors.border}'
    rounded: '{rounded.full}'
  button-primary:
    backgroundColor: '{colors.tertiary}'
    textColor: '{colors.text-on-accent}'
    rounded: '{rounded.md}'
    padding: 10px 18px
    typography: '{typography.body-medium}'
  input:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.text-primary}'
    rounded: '{rounded.md}'
    padding: 10px 14px
    height: '{spacing.input-height}'
    typography: '{typography.input-text}'
  badge-neutral:
    backgroundColor: '{colors.surface-inset}'
    textColor: '{colors.text-secondary}'
    rounded: '{rounded.full}'
    padding: 4px 10px
    typography: '{typography.badge-label}'
  badge-success:
    backgroundColor: '{colors.success-bg}'
    textColor: '{colors.success}'
    rounded: '{rounded.full}'
    padding: 4px 10px
    typography: '{typography.badge-label}'
  badge-warning:
    backgroundColor: '{colors.warning-bg}'
    textColor: '{colors.warning}'
    rounded: '{rounded.full}'
    padding: 4px 10px
    typography: '{typography.badge-label}'
  badge-danger:
    backgroundColor: '{colors.danger-bg}'
    textColor: '{colors.danger}'
    rounded: '{rounded.full}'
    padding: 4px 10px
    typography: '{typography.badge-label}'
  card:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.text-primary}'
    rounded: '{rounded.md}'
    padding: '{spacing.card-padding}'
```

## Do's and Don'ts

- **Do** использовать свитч формата iOS 26 с капсульным вытянутым бегунком 28×22px внутри трека 52×26px.
- **Do** применять мягкие бескаркасные капсулы рисков с иконками Lucide, где цвет иконки строго совпадает с цветом текста через `stroke: currentColor; fill: none`.
- **Do** сохранять нейтральную капсулу `#EFEFF4` с текстом `#6B7280` как базовый стандарт для технических параметров (по образцу «Бензин 1.8L»).
- **Do** передавать hover-состояние карточек и контролов только изменением цвета (контур, фон, акцент текста/стрелки), оставляя базовую тень карточек статичной.
- **Don't** усиливать, размывать или увеличивать тень (`box-shadow`) у карточек при наведении курсора.
- **Don't** делать бегунок свитча круглым (как в iOS 18) при использовании концепта iOS 26.
- **Don't** красить иконки статусов в черный цвет — они всегда наследуют семантический тон капсулы (`#15803D`, `#B45309`, `#B91C1C`, `#1D4ED8`, `#6B7280`).
- **Don't** добавлять обводку 1px вокруг статус-капсул, сохраняя их бескаркасными и воздушными.
