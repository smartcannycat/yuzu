<script setup lang="ts">
import { AlertTriangle, CheckCircle2, OctagonAlert } from '@lucide/vue'
import { computed } from 'vue'

import { CapyMascot } from '@/components/mascot'
import { BaseBadge, BaseCard } from '@/components/ui'
import type { LotDetailResponse, TrafficLightColor } from '@/types/api'

interface Props {
  detail: LotDetailResponse
  isSimulationModified?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSimulationModified: false,
})

const VERDICT_META: Record<
  TrafficLightColor,
  {
    badgeVariant: 'success' | 'warning' | 'danger'
    label: string
    shortTitle: string
  }
> = {
  green: {
    badgeVariant: 'success',
    label: 'Можно брать',
    shortTitle: 'Рекомендуется к покупке',
  },
  yellow: {
    badgeVariant: 'warning',
    label: 'Под вопросом',
    shortTitle: 'Требует проверки сметы и рисков',
  },
  red: {
    badgeVariant: 'danger',
    label: 'Высокий риск',
    shortTitle: 'Покупка не рекомендуется',
  },
}

const verdictMeta = computed(() => VERDICT_META[props.detail.verdict.verdict])
</script>

<template>
  <BaseCard variant="surface" padding="lg">
    <div class="flex items-center gap-3.5">
      <div class="h-[68px] w-[68px] shrink-0 sm:h-[76px] sm:w-[76px]">
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

    <ul v-if="detail.verdict.reasoning_bullets.length > 0" class="mt-3 flex flex-col gap-1.5">
      <li
        v-for="bullet in detail.verdict.reasoning_bullets"
        :key="bullet"
        class="text-text-primary flex items-start gap-2 text-[13px] leading-snug"
      >
        <CheckCircle2
          v-if="detail.verdict.verdict === 'green'"
          :size="15"
          class="text-success mt-0.5 shrink-0"
        />
        <AlertTriangle
          v-else-if="detail.verdict.verdict === 'yellow'"
          :size="15"
          class="text-warning mt-0.5 shrink-0"
        />
        <OctagonAlert v-else :size="15" class="text-danger mt-0.5 shrink-0" />
        <span>{{ bullet }}</span>
      </li>
    </ul>
  </BaseCard>
</template>
