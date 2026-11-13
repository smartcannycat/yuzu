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
      class="border-danger/25 bg-danger-bg text-danger hover:bg-danger-bg/95 focus-visible:outline-danger flex w-full cursor-pointer items-center justify-between gap-3 rounded-md border px-3.5 py-2.5 text-left shadow-sm backdrop-blur-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
      @click="emit('inspect')"
    >
      <div class="flex min-w-0 items-center gap-2.5">
        <span
          aria-hidden="true"
          class="bg-danger/12 flex h-7 w-7 shrink-0 items-center justify-center rounded-sm"
        >
          <OctagonAlert :size="16" :stroke-width="2" />
        </span>
        <div class="min-w-0">
          <div class="text-[12px] font-semibold tracking-[0.02em] uppercase">
            Критическое предупреждение кросс-аудита
          </div>
          <p class="truncate text-[13px] font-medium">
            {{ audit.headline_ru }}
          </p>
        </div>
      </div>

      <span class="inline-flex shrink-0 items-center gap-0.5 text-[12px] font-semibold">
        Подробнее
        <ChevronRight :size="15" :stroke-width="2" />
      </span>
    </button>
  </div>
</template>
