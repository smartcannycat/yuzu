<script setup lang="ts">
import { ref } from 'vue'

import { BaseBadge, BaseCard, BrandLogo } from '@/components/ui'

const logoBoopCount = ref(0)
const MARK_SIZES = [28, 40, 54, 72, 96] as const

function handleLogoBoop(count: number): void {
  logoBoopCount.value = count
}
</script>

<template>
  <BaseCard as="section" padding="lg" class="flex flex-col gap-6">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <div class="flex flex-col gap-0.5">
        <h2 class="text-text-primary text-[19px] leading-snug font-semibold">
          8. Логотип и айдентика («YUZU Identity»)
        </h2>
        <span class="text-text-secondary text-[13px]">
          Живое дыхание, моргание и интерактивная реакция по клику на Капибару Юдзу («Boop»)
        </span>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <BaseBadge v-if="logoBoopCount > 0" variant="success" size="sm">
          Поглаживаний Юдзу: {{ logoBoopCount }}
        </BaseBadge>
        <span class="text-text-muted text-[12px]">Нажмите на капибару в любом логотипе ниже</span>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <BaseCard variant="inset" padding="md" class="flex flex-col justify-between gap-4">
        <div class="flex items-center justify-between gap-2">
          <span class="text-text-secondary text-[12px] font-medium">
            Вариант 1: С Капибарой Юдзу (<code>variant="mascot"</code>)
          </span>
          <BaseBadge variant="warning" size="sm">Основной • Интерактивный</BaseBadge>
        </div>
        <div class="border-border bg-surface flex flex-col gap-4 rounded-sm border p-4">
          <BrandLogo layout="auth" variant="mascot" @boop="handleLogoBoop" />
          <div class="border-border border-t pt-3">
            <BrandLogo layout="header" variant="mascot" @boop="handleLogoBoop" />
          </div>
        </div>
      </BaseCard>

      <BaseCard variant="inset" padding="md" class="flex flex-col justify-between gap-4">
        <div class="flex items-center justify-between gap-2">
          <span class="text-text-secondary text-[12px] font-medium">
            Вариант 2: Чистый текстовый (<code>variant="wordmark"</code>)
          </span>
          <BaseBadge variant="neutral" size="sm">Компактный</BaseBadge>
        </div>
        <div class="border-border bg-surface flex flex-col gap-4 rounded-sm border p-4">
          <BrandLogo layout="auth" variant="wordmark" />
          <div class="border-border border-t pt-3">
            <BrandLogo layout="header" variant="wordmark" />
          </div>
        </div>
      </BaseCard>
    </div>

    <BaseCard variant="inset" padding="md" class="flex flex-col gap-4">
      <div class="flex items-center justify-between gap-2">
        <div class="flex flex-col gap-0.5">
          <span class="text-text-primary text-[14px] font-semibold">
            Знак Капибары Юдзу по пропорциям рига (<code>layout="mark"</code>)
          </span>
          <span class="text-text-secondary text-[12px]">
            Точные пропорции спящей/выглядывающей капибары с юдзу на макушке (без рамки и тени)
          </span>
        </div>
        <BaseBadge variant="success" size="sm">SVG Rig 1:1</BaseBadge>
      </div>

      <div class="border-border bg-surface flex flex-wrap items-end gap-6 rounded-sm border p-5">
        <div
          v-for="markSize in MARK_SIZES"
          :key="markSize"
          class="flex flex-col items-center gap-1.5"
        >
          <BrandLogo layout="mark" :size="markSize" @boop="handleLogoBoop" />
          <span class="text-text-muted font-mono text-[11px]">{{ markSize }}px</span>
        </div>
      </div>
    </BaseCard>

    <BaseCard variant="inset" padding="md" class="flex flex-col gap-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex flex-col gap-0.5">
          <span class="text-text-primary text-[14px] font-semibold">
            OpenGraph-превью на базе <code>stageshow-vue</code> (<code>/og-image.png</code>,
            1200×630)
          </span>
          <span class="text-text-secondary text-[12px]">
            Продуктовый кадр с окном <code>yuzu.auto</code> и сателлитной карточкой вердикта Юдзу
          </span>
        </div>
        <BaseBadge variant="neutral" size="sm">1200×630 Stageshow</BaseBadge>
      </div>

      <div class="border-border bg-surface overflow-hidden rounded-md border">
        <img
          src="/og-image.png"
          alt="YUZU OpenGraph social preview card"
          width="1200"
          height="630"
          class="block h-auto w-full"
        />
      </div>
    </BaseCard>
  </BaseCard>
</template>
