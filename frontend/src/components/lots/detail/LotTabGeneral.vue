<script setup lang="ts">
import {
  AlertTriangle,
  Car,
  CheckCircle2,
  ExternalLink,
  FileSearch,
  History,
  OctagonAlert,
  ShieldAlert,
  SlidersHorizontal,
} from '@lucide/vue'
import { computed } from 'vue'

import { CapyMascot } from '@/components/mascot'
import {
  BaseBadge,
  BaseCard,
  InsetListGroup,
  InsetListItem,
  TtxGrid,
  type TtxItem,
} from '@/components/ui'
import type { FuelType, LotDetailResponse, OdometerStatus, TrafficLightColor } from '@/types/api'
import { formatEngineLiters, formatMileageKm, formatRub } from '@/utils/formatters'

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

const verdictMeta = computed(() => VERDICT_META[props.detail.verdict.verdict])

const turnkeyCostRub = computed(() => props.detail.economics.wise_cost_ladder.turnkey_cost_rub)

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
  const strictnessText = `${auctionTitle} (${passport.auction_strictness_index.toFixed(2)})`

  return [
    {
      label: 'Номер кузова (Frame ID)',
      value: passport.frame_id,
    },
    {
      label: 'Регистрация и коридор ЕАЭС',
      value: passport.first_reg_date_str || String(passport.first_reg_year ?? '—'),
    },
    {
      label: 'Двигатель и мощность',
      value: `${formatEngineLiters(passport.engine_cc)} (${engineStr}) · ${powerStr}`,
    },
    {
      label: 'Пробег и одометр',
      value: mileageValue,
    },
    {
      label: 'КПП и привод',
      value: `${passport.transmission}${drivePart}${fuelPart}`,
    },
    {
      label: 'Цвет и код краски',
      value: colorValue,
    },
    {
      label: 'Оценки аукциона',
      value: gradesValue,
    },
    {
      label: 'Площадка и строгость',
      value: strictnessText,
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
      <!-- Traffic Light Verdict Card -->
      <BaseCard variant="surface" padding="lg">
        <div class="flex items-center gap-3">
          <div class="h-14 w-14 shrink-0">
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

        <!-- Body & Interior Summaries -->
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

        <!-- Key Reasoning Bullets -->
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

      <!-- TTX Card -->
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

    <!-- Secondary Right Column: Turnkey Economics Summary + Quick Rows -->
    <div class="flex min-w-0 flex-col gap-4 lg:col-span-5">
      <BaseCard variant="surface" padding="lg">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-text-secondary text-[13px] font-medium">Себестоимость под ключ</div>
            <div
              class="text-text-primary mt-1 text-[30px] leading-tight font-semibold tracking-[-0.02em] tabular-nums"
            >
              {{ formatRub(turnkeyCostRub) }}
            </div>
          </div>

          <BaseBadge :variant="verdictMeta.badgeVariant">
            {{ detail.verdict.badge_text }}
          </BaseBadge>
        </div>

        <div class="border-border mt-4 flex flex-col gap-2 border-t pt-3.5 text-[14px]">
          <div class="flex items-center justify-between gap-3">
            <span class="text-text-secondary"
              >Рынок РФ (Drom · {{ detail.market.analogs_count }} авто)</span
            >
            <span class="text-text-primary shrink-0 font-semibold whitespace-nowrap tabular-nums">
              {{ formatRub(detail.market.market_price_rf_rub) }}
            </span>
          </div>

          <div
            v-if="detail.market.price_min_rub && detail.market.price_max_rub"
            class="flex items-center justify-between gap-3 text-[13px]"
          >
            <span class="text-text-secondary min-w-0"
              >Разброс в наличии ({{ detail.market.search_region_ru }})</span
            >
            <span class="text-text-secondary shrink-0 whitespace-nowrap tabular-nums">
              {{ formatRub(detail.market.price_min_rub) }} –
              {{ formatRub(detail.market.price_max_rub) }}
            </span>
          </div>

          <div class="flex items-center justify-between gap-3">
            <span class="text-text-secondary">Ремонт в смете Farpost</span>
            <span class="text-text-primary shrink-0 font-medium whitespace-nowrap tabular-nums">
              {{
                detail.economics.is_repairs_included
                  ? formatRub(detail.economics.farpost_repair.grand_total_repair_rub)
                  : 'Исключён (0 ₽)'
              }}
            </span>
          </div>

          <div class="flex items-center justify-between gap-3">
            <span class="text-text-secondary">Доходность (ROI)</span>
            <span
              class="shrink-0 font-semibold whitespace-nowrap tabular-nums"
              :class="detail.verdict.net_benefit_rub >= 0 ? 'text-success' : 'text-danger'"
            >
              {{ detail.verdict.benefit_percentage > 0 ? '+' : ''
              }}{{ detail.verdict.benefit_percentage }}%
            </span>
          </div>
        </div>

        <button
          type="button"
          class="bg-surface-inset hover:bg-surface-hover text-text-primary mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-sm px-3.5 py-2.5 text-[13px] font-medium transition-colors"
          @click="emit('openEconomicsTab')"
        >
          <SlidersHorizontal :size="15" :stroke-width="1.9" />
          <span>Настроить ставку и утильсбор</span>
        </button>
      </BaseCard>

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
