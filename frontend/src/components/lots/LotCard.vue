<script setup lang="ts">
import { AlertTriangle, FileText, ShieldAlert } from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import LotCardMenu from '@/components/lots/LotCardMenu.vue'
import { VERDICT_ICON_MAP } from '@/components/lots/verdictOptions'
import { BaseBadge, BaseCard } from '@/components/ui'
import { useAuthorizedImage } from '@/composables/useAuthorizedImage'
import type { LotSummary } from '@/types/api'
import {
  cleanVerdictText,
  formatArchiveBadgeLabelRu,
  formatCardDateLabel,
  formatEngineLiters,
  formatMileageKm,
  formatRub,
} from '@/utils/formatters'
import { TRAFFIC_LIGHT_META } from '@/utils/lotPresentation'

interface Props {
  lot: LotSummary
  menuOpen?: boolean
  selectionMode?: boolean
  selected?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  menuOpen: false,
  selectionMode: false,
  selected: false,
})

const emit = defineEmits<{
  select: [lot: LotSummary]
  toggleMenu: [lotId: string]
  closeMenu: []
  toggleArchive: [lot: LotSummary]
  deleteLot: [lot: LotSummary]
  startMultiSelect: [lot: LotSummary]
  toggleSelect: [lotId: string]
}>()

const { src: authorizedThumbnailSrc, hasError: thumbnailFetchError } = useAuthorizedImage(
  () => props.lot.thumbnail_url,
)
const imageError = ref(false)

watch([() => props.lot.thumbnail_url, authorizedThumbnailSrc], () => {
  imageError.value = false
})

const verdictMeta = computed(() => TRAFFIC_LIGHT_META[props.lot.verdict])
const verdictIcon = computed(() => VERDICT_ICON_MAP[props.lot.verdict])
const cleanedHeadline = computed(() => cleanVerdictText(props.lot.verdict_headline))
const hasThumbnail = computed(
  () => Boolean(authorizedThumbnailSrc.value) && !thumbnailFetchError.value && !imageError.value,
)
const dateLabel = computed(() => formatCardDateLabel(props.lot.auction_date, props.lot.created_at))
const archiveBadgeLabel = computed(() =>
  formatArchiveBadgeLabelRu(props.lot.is_archived, props.lot.archived_reason),
)

const benefitClass = computed(() => {
  if (props.lot.net_benefit_rub > 0) return 'text-success'
  if (props.lot.net_benefit_rub < 0) return 'text-danger'
  return 'text-text-secondary'
})

const specsLine = computed(() => {
  const parts: string[] = []
  if (props.lot.year) parts.push(String(props.lot.year))
  if (props.lot.engine_cc) parts.push(formatEngineLiters(props.lot.engine_cc))
  if (props.lot.mileage_km !== null) parts.push(formatMileageKm(props.lot.mileage_km))
  parts.push(`${props.lot.auction_house} #${props.lot.lot_number}`)
  if (props.lot.overall_grade) parts.push(`Оценка ${props.lot.overall_grade}`)
  return parts.join(' · ')
})

function handleCardActivate(): void {
  if (props.selectionMode) {
    emit('toggleSelect', props.lot.lot_id)
    return
  }
  emit('select', props.lot)
}

function handleCardSurfaceClick(event: MouseEvent): void {
  const target = event.target as HTMLElement | null
  if (target?.closest('[data-lot-menu], button, a, [role="button"]')) {
    return
  }
  handleCardActivate()
}

function handleSelectionKeydown(event: KeyboardEvent): void {
  if (!props.selectionMode) return
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    handleCardActivate()
  }
}
</script>

<template>
  <BaseCard
    as="article"
    variant="surface"
    padding="none"
    interactive
    class="group relative h-full overflow-visible transition-shadow"
    :class="[
      menuOpen ? 'z-20' : '',
      selectionMode && selected ? 'ring-accent border-accent ring-2' : '',
    ]"
  >
    <div
      class="flex h-full w-full cursor-pointer flex-col justify-between rounded-md text-left"
      @click="handleCardSurfaceClick"
    >
      <div class="flex items-start gap-3.5 p-4 sm:gap-4 sm:p-4">
        <div
          class="bg-surface-inset border-border relative flex h-[94px] w-[68px] shrink-0 items-center justify-center overflow-hidden rounded-sm border"
        >
          <img
            v-if="hasThumbnail"
            :src="authorizedThumbnailSrc"
            :alt="`Аукционный лист ${lot.make} ${lot.model} #${lot.lot_number}`"
            class="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
            loading="lazy"
            @error="imageError = true"
          />
          <div
            v-else
            class="text-text-tertiary flex flex-col items-center gap-1 px-1.5 text-center"
          >
            <FileText :size="18" :stroke-width="1.6" />
            <span class="text-[10px] leading-tight font-medium">Скан листа</span>
          </div>
        </div>

        <div class="flex min-w-0 flex-1 flex-col gap-2">
          <div class="flex items-start justify-between gap-2">
            <component
              :is="selectionMode ? 'div' : 'button'"
              :type="selectionMode ? undefined : 'button'"
              :role="selectionMode ? 'button' : undefined"
              :tabindex="selectionMode ? 0 : undefined"
              :aria-pressed="selectionMode ? selected : undefined"
              class="focus-visible:outline-accent min-w-0 flex-1 cursor-pointer rounded-xs text-left outline-none focus-visible:outline-2 focus-visible:outline-offset-2"
              @click.stop="handleCardActivate"
              @keydown="handleSelectionKeydown"
            >
              <h3
                class="text-text-primary group-hover:text-accent truncate text-[16px] leading-snug font-semibold transition-colors"
              >
                {{ lot.make }} {{ lot.model }}
              </h3>
              <p class="text-text-secondary mt-0.5 truncate text-[12px] leading-snug">
                {{ specsLine }}
              </p>
            </component>

            <LotCardMenu
              :lot="lot"
              :menu-open="menuOpen"
              :selection-mode="selectionMode"
              :selected="selected"
              @toggle-menu="emit('toggleMenu', $event)"
              @close-menu="emit('closeMenu')"
              @toggle-archive="emit('toggleArchive', $event)"
              @delete-lot="emit('deleteLot', $event)"
              @start-multi-select="emit('startMultiSelect', $event)"
            />
          </div>

          <div class="flex flex-wrap items-center gap-1.5">
            <BaseBadge :variant="verdictMeta.badgeVariant" size="sm">
              <template #icon>
                <component :is="verdictIcon" :size="12" :stroke-width="2" />
              </template>
              {{ verdictMeta.label }}
            </BaseBadge>

            <BaseBadge v-if="lot.is_archived" variant="neutral" size="sm">
              {{ archiveBadgeLabel }}
            </BaseBadge>

            <BaseBadge v-if="lot.meti_sanction_risk" variant="warning" size="sm">
              <template #icon>
                <ShieldAlert :size="12" :stroke-width="2" />
              </template>
              METI риск
            </BaseBadge>

            <span
              class="bg-surface-inset text-text-secondary inline-flex min-h-5 items-center rounded-full px-2 py-0.5 font-mono text-[11px] font-medium"
            >
              {{ lot.frame_id }}
            </span>
          </div>

          <div
            class="border-border flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-t pt-2"
          >
            <div>
              <div class="text-text-primary text-[17px] leading-tight font-semibold">
                {{ formatRub(lot.turnkey_cost_rub) }}
              </div>
              <div class="text-text-tertiary mt-0.5 text-[11px] leading-tight">
                под ключ · РФ ~{{ formatRub(lot.market_price_rf_rub) }}
              </div>
            </div>

            <div class="text-right">
              <div class="text-[14px] leading-tight font-semibold" :class="benefitClass">
                {{ formatRub(lot.net_benefit_rub, { signed: true }) }}
              </div>
              <div class="text-text-tertiary mt-0.5 text-[11px] leading-tight">
                {{ dateLabel }}
              </div>
            </div>
          </div>

          <p
            v-if="cleanedHeadline && !lot.has_anomaly"
            class="text-text-secondary line-clamp-1 text-[12px] leading-snug"
          >
            {{ cleanedHeadline }}
          </p>
        </div>
      </div>

      <div
        v-if="lot.has_anomaly && lot.anomaly_text"
        class="bg-danger-bg text-danger border-danger/10 flex items-start gap-2 rounded-b-md border-t px-4 py-2 text-[12px] leading-snug"
      >
        <AlertTriangle :size="14" :stroke-width="2" class="mt-0.5 shrink-0" />
        <span class="line-clamp-2 font-medium">{{ lot.anomaly_text }}</span>
      </div>
    </div>
  </BaseCard>
</template>
