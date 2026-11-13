<script setup lang="ts">
import { ChevronRight, OctagonAlert } from '@lucide/vue'

import type { CrossAuditReport } from '@/types/api'

interface Props {
  audit: CrossAuditReport
}

defineProps<Props>()

const emit = defineEmits<{
  inspect: []
}>()
</script>

<template>
  <div
    v-if="audit.has_critical_anomaly || audit.risk_level === 'CRITICAL'"
    role="alert"
    class="sticky top-2 z-20"
  >
    <button
      type="button"
      class="border-danger/20 bg-danger-bg/95 focus-visible:outline-danger flex w-full cursor-pointer items-center justify-between gap-3 rounded-md border px-3.5 py-2.5 text-left backdrop-blur-md transition-colors hover:bg-[#FEE8E8] focus-visible:outline-2 focus-visible:outline-offset-2"
      @click="emit('inspect')"
    >
      <div class="flex min-w-0 items-center gap-3">
        <span
          aria-hidden="true"
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] bg-[#FF3B30] text-white"
        >
          <OctagonAlert :size="17" :stroke-width="2" />
        </span>
        <div class="min-w-0">
          <div class="text-danger text-[13px] leading-tight font-semibold">
            Критическое предупреждение кросс-аудита
          </div>
          <p class="text-text-primary/85 mt-0.5 truncate text-[12.5px] leading-snug font-normal">
            {{ audit.headline_ru }}
          </p>
        </div>
      </div>

      <span
        class="text-danger inline-flex shrink-0 items-center gap-0.5 text-[12.5px] font-semibold"
      >
        Подробнее
        <ChevronRight :size="15" :stroke-width="2" />
      </span>
    </button>
  </div>
</template>
