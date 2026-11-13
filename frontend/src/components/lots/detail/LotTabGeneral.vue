<script setup lang="ts">
import { Car, ExternalLink, FileSearch, History, ShieldAlert } from '@lucide/vue'
import { computed } from 'vue'

import LotGeneralSummaryCard from '@/components/lots/detail/LotGeneralSummaryCard.vue'
import LotGeneralVerdictCard from '@/components/lots/detail/LotGeneralVerdictCard.vue'
import {
  BaseBadge,
  BaseCard,
  InsetListGroup,
  InsetListItem,
  TtxGrid,
  type TtxItem,
} from '@/components/ui'
import type { FuelType, LotDetailResponse, OdometerStatus } from '@/types/api'
import { formatEngineLiters, formatMileageKm } from '@/utils/formatters'

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

const ODOMETER_LABELS_RU: Record<OdometerStatus, string> = {
  confirmed: 'подтверждён',
  replaced: 'заменён (*)',
  tampered: 'скручен ($)',
  unknown: 'не подтверждён (#)',
}

const FUEL_LABELS_RU: Record<FuelType, string> = {
  gasoline: 'Бензин',
  hybrid: 'Гибрид',
  diesel: 'Дизель',
  ev: 'Электро',
}

const ttxItems = computed<TtxItem[]>(() => {
  const { passport, audit } = props.detail
  const engineStr = passport.engine_cc ? `${passport.engine_cc.toLocaleString('ru-RU')} см³` : '—'
  const powerStr = passport.power_hp
    ? `${passport.power_hp} л.с.${passport.is_under_160_hp ? ' (≤ 160)' : ' (> 160)'}`
    : 'не указана'

  const mileageValue =
    passport.mileage_km !== null
      ? `${formatMileageKm(passport.mileage_km)} · ${ODOMETER_LABELS_RU[passport.odometer_status]}`
      : '—'

  const drivePart = passport.drive_type ? ` · ${passport.drive_type}` : ''
  const fuelPart = passport.fuel_type ? ` · ${FUEL_LABELS_RU[passport.fuel_type]}` : ''
  const colorValue = passport.color_ru
    ? passport.paint_code
      ? `${passport.color_ru} (${passport.paint_code})`
      : passport.color_ru
    : (passport.paint_code ?? '—')

  const gradesValue = [
    `Общая ${passport.overall_grade}`,
    passport.exterior_grade ? `Кузов ${passport.exterior_grade}` : null,
    passport.interior_grade ? `Салон ${passport.interior_grade}` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  const auctionTitle = passport.auction_branch || passport.auction_house

  return [
    { label: 'Номер кузова (Frame ID)', value: passport.frame_id },
    {
      label: 'Регистрация и коридор ЕАЭС',
      value: passport.first_reg_date_str || String(passport.first_reg_year ?? '—'),
    },
    {
      label: 'Двигатель и мощность',
      value: `${formatEngineLiters(passport.engine_cc)} (${engineStr}) · ${powerStr}`,
    },
    { label: 'Пробег и одометр', value: mileageValue },
    { label: 'КПП и привод', value: `${passport.transmission}${drivePart}${fuelPart}` },
    { label: 'Цвет и код краски', value: colorValue },
    { label: 'Оценки аукциона', value: gradesValue },
    {
      label: 'Площадка и строгость',
      value: `${auctionTitle} (${passport.auction_strictness_index.toFixed(2)})`,
    },
    {
      label: 'Код модели (Katashiki)',
      value: `${passport.model_code} · торгов в архиве: ${audit.times_auctioned}`,
      span: 2,
    },
  ]
})

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
