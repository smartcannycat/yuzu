<script setup lang="ts">
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
    title="Замечания инспектора аукциона"
    :subtitle="`${detail.passport.auction_house} #${detail.passport.lot_number}`"
    max-width="md"
  >
    <div class="flex flex-col gap-4">
      <div class="flex flex-col gap-2">
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Перевод комментариев эксперта
        </h4>
        <ul v-if="detail.passport.inspector_notes_ru.length > 0" class="flex flex-col gap-2">
          <li
            v-for="note in detail.passport.inspector_notes_ru"
            :key="note"
            class="border-border bg-surface rounded-sm border px-3 py-2.5 text-[13px] leading-relaxed text-[#111827]"
          >
            {{ note }}
          </li>
        </ul>
        <p v-else class="text-text-secondary text-[13px]">Дополнительных заметок не указано.</p>
      </div>

      <div v-if="detail.passport.seller_comments_ru.length > 0" class="flex flex-col gap-2">
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Примечания продавца
        </h4>
        <ul class="flex flex-col gap-1.5">
          <li
            v-for="comment in detail.passport.seller_comments_ru"
            :key="comment"
            class="bg-surface-inset rounded-sm px-3 py-2 text-[13px] text-[#111827]"
          >
            {{ comment }}
          </li>
        </ul>
      </div>

      <div v-if="detail.passport.inspector_notes_raw.length > 0" class="flex flex-col gap-2">
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Оригинальный японский текст
        </h4>
        <ul
          class="bg-surface-inset flex flex-col gap-1 rounded-sm p-3 font-mono text-[12px] text-[#4B5563]"
        >
          <li v-for="raw in detail.passport.inspector_notes_raw" :key="raw">• {{ raw }}</li>
        </ul>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="open = false">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
