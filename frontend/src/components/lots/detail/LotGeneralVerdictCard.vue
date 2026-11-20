<script setup lang="ts">
import { computed } from 'vue'

import { VERDICT_META } from '@/components/lots/detail/lotPresentation'
import LotVerdictBullets from '@/components/lots/detail/LotVerdictBullets.vue'
import { CapyMascot } from '@/components/mascot'
import { BaseBadge, BaseCard } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'

interface Props {
  detail: LotDetailResponse
  isSimulationModified?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSimulationModified: false,
})

const verdictMeta = computed(() => VERDICT_META[props.detail.verdict.verdict])
</script>

<template>
  <BaseCard variant="surface" padding="lg">
    <div class="flex items-center gap-4">
      <div class="h-[80px] w-[80px] shrink-0 sm:h-[92px] sm:w-[92px]">
        <CapyMascot :verdict="detail.verdict.verdict" size="compact" />
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-1.5">
          <BaseBadge :variant="verdictMeta.badgeVariant">
            {{ verdictMeta.label }}
          </BaseBadge>
          <BaseBadge v-if="detail.economics.customs.meti_sanction_risk" variant="warning">
            METI риск
          </BaseBadge>
          <BaseBadge v-if="isSimulationModified" variant="info">Симуляция</BaseBadge>
        </div>

        <h2 class="text-text-primary mt-1.5 text-[16px] leading-snug font-semibold">
          {{ verdictMeta.shortTitle }}
        </h2>
      </div>
    </div>

    <div class="mt-3.5 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      <div class="bg-surface-inset rounded-sm p-3">
        <div class="text-text-secondary text-[12px] font-medium">Кузов</div>
        <p class="text-text-primary mt-1 text-[13px] leading-relaxed">
          {{ detail.verdict.body_summary_ru }}
        </p>
      </div>

      <div class="bg-surface-inset rounded-sm p-3">
        <div class="text-text-secondary text-[12px] font-medium">Салон</div>
        <p class="text-text-primary mt-1 text-[13px] leading-relaxed">
          {{ detail.verdict.interior_summary_ru }}
        </p>
      </div>
    </div>

    <LotVerdictBullets
      :verdict="detail.verdict.verdict"
      :bullets="detail.verdict.reasoning_bullets"
    />
  </BaseCard>
</template>
