<script setup lang="ts">
import { Loader2, ZoomIn, ZoomOut } from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import { BaseButton, BottomSheet } from '@/components/ui'
import { useAuthorizedImage } from '@/composables/useAuthorizedImage'
import type { LotDetailResponse } from '@/types/api'

interface Props {
  detail: LotDetailResponse
}

const props = defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })
const zoomPercent = ref<100 | 150 | 200>(100)
const imgElementError = ref(false)

const {
  src: authorizedScanSrc,
  isLoading: isLoadingScan,
  hasError: scanFetchError,
} = useAuthorizedImage(() => (open.value ? props.detail.media.sheet_scan_url : null))

watch([open, () => props.detail.media.sheet_scan_url, authorizedScanSrc], ([isOpen]) => {
  if (isOpen) {
    zoomPercent.value = 100
  }
  imgElementError.value = false
})

const hasVisibleScan = computed(
  () => Boolean(authorizedScanSrc.value) && !scanFetchError.value && !imgElementError.value,
)

function cycleZoom(): void {
  if (!hasVisibleScan.value || isLoadingScan.value) return
  zoomPercent.value = zoomPercent.value === 100 ? 150 : zoomPercent.value === 150 ? 200 : 100
}
</script>

<template>
  <BottomSheet
    v-model:open="open"
    title="Оригинальный аукционный лист"
    :subtitle="`${detail.passport.auction_house} #${detail.passport.lot_number} · ${detail.passport.frame_id}`"
    max-width="lg"
  >
    <div class="flex flex-col gap-3">
      <div class="flex items-center justify-between gap-2">
        <span class="text-text-secondary text-[12px]">Масштаб просмотра: {{ zoomPercent }}%</span>
        <BaseButton
          variant="secondary"
          size="sm"
          pill
          :disabled="!hasVisibleScan || isLoadingScan"
          @click="cycleZoom"
        >
          <template #icon-left>
            <ZoomOut v-if="zoomPercent === 200" :size="14" />
            <ZoomIn v-else :size="14" />
          </template>
          {{ zoomPercent === 200 ? 'Сбросить масштаб' : 'Увеличить' }}
        </BaseButton>
      </div>

      <div class="border-border bg-surface-inset max-h-[64vh] overflow-auto rounded-sm border p-2">
        <div
          v-if="isLoadingScan"
          class="text-text-secondary flex items-center justify-center gap-2 py-8 text-[13px]"
        >
          <Loader2 :size="16" class="text-accent animate-spin" />
          <span>Загружаем скан аукционного листа...</span>
        </div>
        <img
          v-else-if="hasVisibleScan"
          :src="authorizedScanSrc"
          :alt="`Аукционный лист ${detail.passport.make} ${detail.passport.model} #${detail.passport.lot_number}`"
          class="mx-auto block rounded-xs transition-all duration-150"
          :style="{ width: `${zoomPercent}%`, maxWidth: 'none' }"
          @error="imgElementError = true"
        />
        <p v-else class="text-text-secondary py-8 text-center text-[13px]">
          Скан аукционного листа недоступен.
        </p>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="open = false">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
