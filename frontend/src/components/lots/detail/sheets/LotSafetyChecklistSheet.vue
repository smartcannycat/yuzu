<script setup lang="ts">
import { AlertTriangle, CheckCircle2, OctagonAlert } from '@lucide/vue'

import { BaseButton, BottomSheet } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'

interface Props {
  detail: LotDetailResponse
}

defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })
</script>

<template>
  <BottomSheet
    v-model:open="open"
    title="Системы безопасности"
    :subtitle="`Итоговый статус: ${detail.safety_checklist.overall_label_ru}`"
    max-width="md"
  >
    <ul class="flex flex-col gap-2.5">
      <li
        v-for="item in detail.safety_checklist.items"
        :key="item.system_key"
        class="border-border bg-surface flex items-start gap-3 rounded-sm border p-3"
      >
        <CheckCircle2 v-if="item.status === 'ok'" :size="18" class="text-success mt-0.5 shrink-0" />
        <AlertTriangle
          v-else-if="item.status === 'warning'"
          :size="18"
          class="text-warning mt-0.5 shrink-0"
        />
        <OctagonAlert v-else :size="18" class="text-danger mt-0.5 shrink-0" />

        <div class="min-w-0 flex-1">
          <div class="text-text-primary text-[14px] font-semibold">{{ item.label_ru }}</div>
          <p class="text-text-secondary mt-0.5 text-[13px] leading-snug">{{ item.detail_ru }}</p>
        </div>
      </li>
    </ul>

    <template #footer>
      <BaseButton variant="primary" block @click="open = false">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
