<script setup lang="ts">
import { Car, ExternalLink, FileSearch, History, ShieldAlert } from '@lucide/vue'
import { computed } from 'vue'

import LotGeneralSummaryCard from '@/components/lots/detail/LotGeneralSummaryCard.vue'
import LotGeneralVerdictCard from '@/components/lots/detail/LotGeneralVerdictCard.vue'
import { buildLotTtxItems } from '@/components/lots/detail/lotPresentation'
import { BaseBadge, BaseCard, InsetListGroup, InsetListItem, TtxGrid } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'

interface Props {
  detail: LotDetailResponse
  isSimulationModified?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSimulationModified: false,
})

const emit = defineEmits<{
  openScan: []
  openAuditHistory: []
  openEconomicsTab: []
}>()

const ttxItems = computed(() => buildLotTtxItems(props.detail))

const auditSubtitle = computed(() => {
  const count = props.detail.audit.times_auctioned
  if (props.detail.audit.has_critical_anomaly) {
    return `${count} торг(а) · выявлены критические расхождения`
  }
  if (props.detail.audit.anomalies.length > 0) {
    return `${count} торг(а) · есть замечания аудита`
  }
  return `${count} торг(а) · расхождений не выявлено`
})
</script>

<template>
  <div class="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:items-start lg:gap-5">
    <!-- Primary Left Column: Verdict + TTX -->
    <div class="flex min-w-0 flex-col gap-4 lg:col-span-7">
      <LotGeneralVerdictCard :detail="detail" :is-simulation-modified="isSimulationModified" />

      <BaseCard variant="surface" padding="lg">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h3 class="text-text-primary text-[16px] font-semibold">Паспорт и ТТХ</h3>
          <span class="text-text-secondary text-[12px]">
            Лот #{{ detail.passport.lot_number }}
          </span>
        </div>

        <TtxGrid :items="ttxItems" :columns="2" />

        <div v-if="detail.passport.equipment_ru.length > 0" class="mt-3.5 flex flex-wrap gap-1.5">
          <BaseBadge v-for="option in detail.passport.equipment_ru" :key="option" variant="neutral">
            {{ option }}
          </BaseBadge>
        </div>
      </BaseCard>
    </div>

    <!-- Secondary Right Column: Turnkey Economics Summary + Documents & Market -->
    <div class="flex min-w-0 flex-col gap-4 lg:col-span-5">
      <LotGeneralSummaryCard :detail="detail" @open-economics-tab="emit('openEconomicsTab')" />

      <InsetListGroup title="Документы и рынок">
        <InsetListItem
          title="Оригинальный аукционный лист"
          subtitle="Открыть скан в полном размере"
          value="Скан"
          squircle-color="#007AFF"
          interactive
          chevron
          @click="emit('openScan')"
        >
          <template #icon>
            <FileSearch :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>

        <InsetListItem
          title="Сравнить с рынком на Drom.ru"
          :subtitle="`В наличии · ${detail.market.search_region_ru}`"
          :value="`${detail.market.analogs_count} авто`"
          squircle-color="#FF9500"
          :href="detail.media.drom_search_url"
          chevron
        >
          <template #icon>
            <ExternalLink :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>

        <InsetListItem
          title="История торгов в Японии"
          :subtitle="auditSubtitle"
          :value="detail.audit.has_critical_anomaly ? 'Риск' : `${detail.audit.times_auctioned}`"
          :squircle-color="detail.audit.has_critical_anomaly ? '#FF3B30' : '#34C759'"
          interactive
          chevron
          @click="emit('openAuditHistory')"
        >
          <template #icon>
            <ShieldAlert v-if="detail.audit.has_critical_anomaly" :size="16" :stroke-width="2" />
            <History v-else :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>
      </InsetListGroup>

      <div
        v-if="detail.passport.ocr_warnings.length > 0"
        class="bg-warning-bg text-warning border-warning/20 flex items-start gap-2 rounded-md border px-3.5 py-2.5 text-[12px] leading-snug"
      >
        <Car :size="15" class="mt-0.5 shrink-0" />
        <span>{{ detail.passport.ocr_warnings.join(' · ') }}</span>
      </div>
    </div>
  </div>
</template>
