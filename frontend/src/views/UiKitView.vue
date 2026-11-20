<script setup lang="ts">
import { ArrowLeft, SlidersHorizontal, Sparkles } from '@lucide/vue'
import { onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'

import { BaseBadge, BaseButton } from '@/components/ui'
import {
  UiKitBadgesAndListsSection,
  UiKitBrandSection,
  UiKitButtonsSection,
  UiKitDemoSheet,
  UiKitInputsSection,
  UiKitMascotSection,
  UiKitTtxAndLadderSection,
} from '@/components/uikit'

const router = useRouter()

const isPersonalUtil = ref(true)
const isCalculating = ref(false)
const isSheetOpen = ref(false)
const activeSheetTopic = ref<'auction' | 'farpost'>('auction')

let calcDemoTimerId: number | null = null

function clearLoadingDemoTimer(): void {
  if (calcDemoTimerId !== null && typeof window !== 'undefined') {
    window.clearTimeout(calcDemoTimerId)
    calcDemoTimerId = null
  }
}

function triggerLoadingDemo(): void {
  if (isCalculating.value || typeof window === 'undefined') return
  isCalculating.value = true
  calcDemoTimerId = window.setTimeout(() => {
    calcDemoTimerId = null
    isCalculating.value = false
  }, 1200)
}

function openDetailsSheet(topic: 'auction' | 'farpost'): void {
  activeSheetTopic.value = topic
  isSheetOpen.value = true
}

function goHome(): void {
  void router.push({ name: 'home' })
}

onBeforeUnmount(() => {
  clearLoadingDemoTimer()
})
</script>

<template>
  <div class="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-10">
    <header class="border-border flex flex-wrap items-center justify-between gap-4 border-b pb-5">
      <div class="flex flex-col gap-1">
        <div class="flex items-center gap-2">
          <BaseButton variant="ghost" size="sm" @click="goHome">
            <template #icon-left>
              <ArrowLeft :size="15" :stroke-width="2" />
            </template>
            Назад
          </BaseButton>
          <BaseBadge variant="info" size="sm">
            <template #icon>
              <Sparkles :size="12" :stroke-width="2" />
            </template>
            Clean Light v2.2
          </BaseBadge>
        </div>
        <h1 class="mt-1 text-[24px] leading-tight font-semibold tracking-[-0.015em] sm:text-[28px]">
          YUZU Component Library
        </h1>
        <p class="text-text-secondary text-[14px]">
          SF Pro Display • Lucide Icons • iOS 26 Switch • Bottom Sheet • WCAG AA & Adaptive
        </p>
      </div>

      <BaseButton variant="primary" size="md" @click="openDetailsSheet('auction')">
        <template #icon-left>
          <SlidersHorizontal :size="16" :stroke-width="2" />
        </template>
        Открыть Bottom Sheet
      </BaseButton>
    </header>

    <UiKitButtonsSection :is-calculating="isCalculating" @trigger-loading="triggerLoadingDemo" />
    <UiKitInputsSection v-model:is-personal-util="isPersonalUtil" />
    <UiKitBadgesAndListsSection @open-sheet="openDetailsSheet" />
    <UiKitTtxAndLadderSection :is-personal-util="isPersonalUtil" />
    <UiKitMascotSection />
    <UiKitBrandSection />

    <UiKitDemoSheet v-model:open="isSheetOpen" :topic="activeSheetTopic" />
  </div>
</template>
