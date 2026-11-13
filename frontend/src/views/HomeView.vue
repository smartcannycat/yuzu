<script setup lang="ts">
import { ArrowRight, Layers, ShieldCheck, Sparkles } from '@lucide/vue'
import { useRouter } from 'vue-router'

import { BaseBadge, BaseButton, BaseCard, InsetListGroup, InsetListItem } from '@/components/ui'

const router = useRouter()

function openUiKit() {
  void router.push({ name: 'ui-kit' })
}
</script>

<template>
  <main
    class="mx-auto flex min-h-screen w-full max-w-[680px] flex-col justify-center gap-6 px-4 py-10"
  >
    <BaseCard padding="lg" class="flex flex-col gap-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <BaseBadge variant="info">
          <template #icon>
            <Sparkles :size="14" :stroke-width="2" />
          </template>
          YUZU Clean Light
        </BaseBadge>
        <span class="text-text-secondary text-[12px] font-medium">Vue 3 + Tailwind v4</span>
      </div>

      <div class="flex flex-col gap-2">
        <h1 class="text-text-primary text-[28px] leading-tight font-semibold tracking-[-0.02em]">
          YUZU // Интеллект японских автоаукционов
        </h1>
        <p class="text-text-secondary text-[15px] leading-relaxed">
          Базовая дизайн-система Clean Light, типографика SF Pro Display, иконки Lucide и доступные
          интерактивные компоненты готовы к сборке продуктовых экранов.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <BaseButton variant="primary" size="lg" @click="openUiKit">
          <span>Открыть UI-кит</span>
          <template #icon-right>
            <ArrowRight :size="18" :stroke-width="2" />
          </template>
        </BaseButton>
      </div>
    </BaseCard>

    <InsetListGroup title="Быстрая навигация">
      <InsetListItem
        title="Витрина базовых компонентов"
        subtitle="Кнопки, поля ввода, свитч iOS 26, Bottom Sheet, ТТХ и лестница"
        value="/ui-kit"
        squircle-color="#FF6B00"
        :to="{ name: 'ui-kit' }"
        chevron
      >
        <template #icon>
          <Layers :size="17" :stroke-width="2" />
        </template>
      </InsetListItem>
      <InsetListItem
        title="Доступность и адаптив"
        subtitle="Focus-visible, ARIA, prefers-reduced-motion, 320px–1200px"
        value="WCAG AA"
        squircle-color="#15803D"
      >
        <template #icon>
          <ShieldCheck :size="17" :stroke-width="2" />
        </template>
      </InsetListItem>
    </InsetListGroup>
  </main>
</template>
