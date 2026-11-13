<script setup lang="ts">
import { AlertTriangle, CheckCircle2, OctagonAlert } from '@lucide/vue'
import { computed } from 'vue'

import BrandLogo from '@/components/brand/BrandLogo.vue'
import LotBodyDiagram from '@/components/lots/detail/LotBodyDiagram.vue'
import { getDefectTone } from '@/components/lots/detail/lotDefects'
import {
  VERDICT_META,
  buildActiveRiskLabels,
  buildCostLadderSteps,
  buildLotTtxItems,
} from '@/components/lots/detail/lotPresentation'
import { CapyMascot } from '@/components/mascot'
import { BaseBadge, CostLadder, TtxGrid } from '@/components/ui'
import type { ChecklistItemStatus, LotDetailResponse, SafetyCheckItem } from '@/types/api'
import { formatEngineLiters, formatMileageKm, formatRub } from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
  isSimulationModified?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSimulationModified: false,
})

const verdictMeta = computed(() => VERDICT_META[props.detail.verdict.verdict])
const ttxItems = computed(() => buildLotTtxItems(props.detail, { katashikiSpan: 1 }))
const riskChips = computed(() => buildActiveRiskLabels(props.detail.passport.risk_flags))

const ladderSteps = computed(() => {
  const { economics } = props.detail
  return buildCostLadderSteps(economics.wise_cost_ladder.steps, {
    bidJpy: economics.wise_cost_ladder.car_bid_jpy,
    jpyRate: economics.customs.rates_snapshot.jpy_rub_bank || 0.64,
    includeRepairs: economics.is_repairs_included,
  })
})

const spreadAbsRub = computed(() =>
  Math.abs(props.detail.economics.wise_cost_ladder.net_benefit_rub),
)
const isOverpay = computed(() => props.detail.economics.wise_cost_ladder.net_benefit_rub < 0)

const spreadLabel = computed(() =>
  isOverpay.value
    ? `Переплата: ${formatRub(spreadAbsRub.value)}`
    : `Выгода: ${formatRub(spreadAbsRub.value)}`,
)

const roiFormatted = computed(() => {
  const pct = props.detail.economics.wise_cost_ladder.benefit_percentage
  return `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`
})

const dromRangeText = computed(() => {
  const { price_min_rub: minRub, price_max_rub: maxRub } = props.detail.market
  if (minRub && maxRub) return `${formatRub(minRub)} – ${formatRub(maxRub)}`
  return props.detail.market.search_region_ru
})

const repairTotalRub = computed(() => props.detail.economics.farpost_repair.grand_total_repair_rub)

const utilModeLabel = computed(() => {
  const { customs } = props.detail.economics
  if (customs.is_commercial_util) return 'Коммерческий тариф (ПП РФ № 1255)'
  if (customs.is_under_160_hp === false) return 'Повышенный тариф (> 160 л.с.)'
  return 'Льготный для физлица (≤ 160 л.с.)'
})

const reportDateLabel = computed(() =>
  new Date().toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }),
)

const CHECKLIST_BADGE_META: Record<
  ChecklistItemStatus,
  { variant: 'success' | 'warning' | 'danger'; label: string }
> = {
  ok: { variant: 'success', label: 'Норма' },
  warning: { variant: 'warning', label: 'Риск' },
  critical: { variant: 'danger', label: 'Критично' },
}

const SAFETY_SHORT_LABELS: Record<SafetyCheckItem['system_key'], string> = {
  structural_frame: 'Каркас и лонжероны',
  airbags_srs: 'Подушки SRS',
  engine_transmission: 'Двигатель и КПП',
  underbody_corrosion: 'Днище и коррозия',
  flood_or_fire: 'Признаки затопления / градобоя',
}
</script>

<template>
  <article class="hidden bg-white px-[12mm] text-[#111827] print:block">
    <!-- PAGE 1: Brand Lockup + Vehicle Header + Cross-Audit + Verdict & Summary + TTX + Safety & History -->
    <div class="pt-[9mm] pb-[6mm]">
      <header class="flex flex-col gap-2.5 border-b border-[#E5E5EA] pb-2.5">
        <div
          class="flex items-center justify-between gap-4 rounded-md border border-[#E5E5EA] bg-[#F8F8FA] px-3.5 py-2.5"
        >
          <BrandLogo layout="report" :size="40" :animated="false" />

          <div class="flex shrink-0 flex-col items-end gap-1 text-right">
            <span
              class="rounded-sm border border-[#E5E5EA] bg-white px-2.5 py-0.5 font-mono text-[11px] font-semibold text-[#111827]"
            >
              {{ detail.passport.frame_id }}
            </span>
            <span class="text-[10.5px] font-medium text-[#6B7280]">
              Отчёт от {{ reportDateLabel }}
            </span>
          </div>
        </div>

        <div class="flex items-baseline justify-between gap-4">
          <div class="min-w-0">
            <h1 class="text-[21px] leading-tight font-semibold tracking-[-0.015em]">
              {{ detail.passport.make }} {{ detail.passport.model }}
              <span v-if="detail.passport.trim" class="text-[15px] font-normal text-[#4B5563]">
                {{ detail.passport.trim }}
              </span>
            </h1>
            <p class="mt-0.5 text-[11.5px] text-[#6B7280]">
              {{ detail.passport.first_reg_year ?? '—' }} ·
              {{ formatEngineLiters(detail.passport.engine_cc) }} ·
              {{ formatMileageKm(detail.passport.mileage_km) }} ·
              {{ detail.passport.auction_house }} #{{ detail.passport.lot_number }}
            </p>
          </div>

          <BaseBadge v-if="isSimulationModified" variant="info" class="shrink-0">
            Расчёт скорректирован вручную
          </BaseBadge>
        </div>
      </header>

      <!-- Cross-Audit Warning Banner -->
      <div
        v-if="detail.audit.has_critical_anomaly || detail.audit.anomalies.length > 0"
        class="mt-3 flex break-inside-avoid items-start gap-2.5 rounded-md border px-3 py-2"
        :class="
          detail.audit.has_critical_anomaly
            ? 'border-[#EF4444]/30 bg-[#FEF2F2]'
            : 'border-[#F59E0B]/35 bg-[#FFFBEB]'
        "
      >
        <OctagonAlert
          v-if="detail.audit.has_critical_anomaly"
          :size="15"
          class="mt-0.5 shrink-0 text-[#B91C1C]"
        />
        <AlertTriangle v-else :size="15" class="mt-0.5 shrink-0 text-[#B45309]" />
        <div class="min-w-0 text-[11.5px] leading-snug">
          <span
            class="font-semibold"
            :class="detail.audit.has_critical_anomaly ? 'text-[#B91C1C]' : 'text-[#B45309]'"
          >
            Кросс-аудит ({{ detail.audit.times_auctioned }} торг.):
          </span>
          <span class="text-[#111827]">{{ detail.audit.headline_ru }}</span>
        </div>
      </div>

      <!-- Bento Row 1: Verdict (7 cols) + Financial Summary (5 cols) -->
      <section class="mt-3 grid grid-cols-12 items-stretch gap-3">
        <div
          class="col-span-7 flex break-inside-avoid flex-col justify-between rounded-md border border-[#E5E5EA] bg-white p-3.5"
        >
          <div>
            <div class="flex items-center gap-3">
              <div class="h-[64px] w-[64px] shrink-0">
                <CapyMascot :verdict="detail.verdict.verdict" size="compact" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-1">
                  <BaseBadge :variant="verdictMeta.badgeVariant">
                    {{ verdictMeta.label }}
                  </BaseBadge>
                  <BaseBadge v-if="detail.economics.customs.meti_sanction_risk" variant="warning">
                    METI риск
                  </BaseBadge>
                </div>
                <h2 class="mt-1 text-[14px] leading-snug font-semibold">
                  {{ verdictMeta.shortTitle }}
                </h2>
              </div>
            </div>

            <div class="mt-2.5 grid grid-cols-2 gap-2">
              <div class="rounded-sm bg-[#F8F8FA] p-2.5">
                <div class="text-[10.5px] font-medium text-[#6B7280]">Кузов</div>
                <p class="mt-0.5 text-[11.5px] leading-snug text-[#111827]">
                  {{ detail.verdict.body_summary_ru }}
                </p>
              </div>
              <div class="rounded-sm bg-[#F8F8FA] p-2.5">
                <div class="text-[10.5px] font-medium text-[#6B7280]">Салон</div>
                <p class="mt-0.5 text-[11.5px] leading-snug text-[#111827]">
                  {{ detail.verdict.interior_summary_ru }}
                </p>
              </div>
            </div>
          </div>

          <ul v-if="detail.verdict.reasoning_bullets.length > 0" class="mt-2.5 flex flex-col gap-1">
            <li
              v-for="bullet in detail.verdict.reasoning_bullets"
              :key="bullet"
              class="flex items-start gap-1.5 text-[11.5px] leading-snug text-[#111827]"
            >
              <CheckCircle2
                v-if="detail.verdict.verdict === 'green'"
                :size="13"
                class="mt-0.5 shrink-0 text-[#15803D]"
              />
              <AlertTriangle
                v-else-if="detail.verdict.verdict === 'yellow'"
                :size="13"
                class="mt-0.5 shrink-0 text-[#B45309]"
              />
              <OctagonAlert v-else :size="13" class="mt-0.5 shrink-0 text-[#B91C1C]" />
              <span>{{ bullet }}</span>
            </li>
          </ul>
        </div>

        <div
          class="col-span-5 flex break-inside-avoid flex-col justify-between rounded-md border border-[#E5E5EA] bg-white p-3.5"
        >
          <div>
            <div class="flex flex-wrap items-center justify-between gap-1.5">
              <div class="text-[11px] font-medium whitespace-nowrap text-[#6B7280]">
                Себестоимость под ключ
              </div>
              <BaseBadge :variant="isOverpay ? 'danger' : 'success'" class="shrink-0">
                {{ spreadLabel }}
              </BaseBadge>
            </div>
            <div
              class="mt-1 text-[21px] leading-tight font-semibold whitespace-nowrap tabular-nums"
            >
              {{ formatRub(detail.economics.wise_cost_ladder.turnkey_cost_rub) }}
            </div>

            <dl class="mt-2.5 divide-y divide-[#F2F2F7] border-t border-[#F2F2F7] text-[11.5px]">
              <div class="flex items-center justify-between gap-2 py-1.5">
                <dt class="text-[#6B7280]">Ставка на аукционе</dt>
                <dd class="font-semibold tabular-nums">
                  {{
                    Math.round(detail.economics.wise_cost_ladder.car_bid_jpy).toLocaleString(
                      'ru-RU',
                    )
                  }}
                  ¥
                </dd>
              </div>
              <div class="flex items-center justify-between gap-2 py-1.5">
                <dt class="text-[#6B7280]">
                  Рынок РФ (Drom · {{ detail.market.analogs_count }} авто)
                </dt>
                <dd class="font-semibold tabular-nums">
                  {{ formatRub(detail.market.market_price_rf_rub) }}
                </dd>
              </div>
              <div class="flex items-center justify-between gap-2 py-1.5">
                <dt class="text-[#6B7280]">Разброс цен в ДФО</dt>
                <dd class="text-right font-medium text-[#374151] tabular-nums">
                  {{ dromRangeText }}
                </dd>
              </div>
              <div class="flex items-center justify-between gap-2 py-1.5">
                <dt class="text-[#6B7280]">Ремонт Farpost</dt>
                <dd class="font-semibold tabular-nums">{{ formatRub(repairTotalRub) }}</dd>
              </div>
              <div class="flex items-center justify-between gap-2 py-1.5">
                <dt class="text-[#6B7280]">Доходность (ROI)</dt>
                <dd
                  class="font-semibold tabular-nums"
                  :class="isOverpay ? 'text-[#B91C1C]' : 'text-[#15803D]'"
                >
                  {{ roiFormatted }}
                </dd>
              </div>
            </dl>
          </div>

          <div class="mt-2 rounded-sm bg-[#F8F8FA] px-2.5 py-2 text-[11px] text-[#4B5563]">
            <div class="font-medium text-[#111827]">Утильсбор: {{ utilModeLabel }}</div>
            <div class="mt-0.5">
              Смета ремонта:
              {{ detail.economics.is_repairs_included ? 'учтена в цене' : 'исключена' }}
            </div>
          </div>
        </div>
      </section>

      <!-- Bento Row 2: Full-width 3x3 TTX Passport + Equipment -->
      <section
        class="mt-2.5 break-inside-avoid rounded-md border border-[#E5E5EA] bg-white p-3 [&_dd]:text-[13px] [&_dl]:gap-x-4 [&_dl]:gap-y-2 [&_dl]:p-2.5 [&_dt]:text-[11px]"
      >
        <div class="mb-1.5 flex items-center justify-between">
          <h2 class="text-[13.5px] font-semibold">Паспорт и ТТХ</h2>
          <span class="text-[11px] text-[#6B7280]">Лот #{{ detail.passport.lot_number }}</span>
        </div>

        <TtxGrid :items="ttxItems" :columns="3" />

        <div v-if="detail.passport.equipment_ru.length > 0" class="mt-2 flex flex-wrap gap-1">
          <BaseBadge v-for="item in detail.passport.equipment_ru" :key="item" variant="neutral">
            {{ item }}
          </BaseBadge>
        </div>
      </section>

      <!-- Bento Row 3: Safety Systems (7 cols) + Auction History (5 cols) -->
      <section class="mt-2.5 grid grid-cols-12 items-stretch gap-2.5">
        <div
          class="col-span-7 flex break-inside-avoid flex-col justify-between rounded-md border border-[#E5E5EA] bg-white p-3"
        >
          <div class="mb-2 flex items-center justify-between gap-2">
            <h2 class="text-[13px] font-semibold">Системы безопасности и каркас</h2>
            <BaseBadge
              :variant="CHECKLIST_BADGE_META[detail.safety_checklist.overall_status].variant"
            >
              {{ detail.safety_checklist.overall_label_ru }}
            </BaseBadge>
          </div>

          <ul class="grid grid-cols-2 gap-1.5 text-[10.5px]">
            <li
              v-for="item in detail.safety_checklist.items"
              :key="item.system_key"
              class="flex items-center justify-between gap-1.5 rounded-sm bg-[#F8F8FA] px-2 py-1"
              :class="item.system_key === 'flood_or_fire' ? 'col-span-2' : ''"
            >
              <span class="truncate font-medium text-[#111827]">
                {{ SAFETY_SHORT_LABELS[item.system_key] ?? item.label_ru }}
              </span>
              <BaseBadge :variant="CHECKLIST_BADGE_META[item.status].variant" class="shrink-0">
                {{ CHECKLIST_BADGE_META[item.status].label }}
              </BaseBadge>
            </li>
          </ul>
        </div>

        <div
          class="col-span-5 flex break-inside-avoid flex-col justify-between rounded-md border border-[#E5E5EA] bg-white p-3"
        >
          <div>
            <div class="mb-1.5 flex items-center justify-between gap-2">
              <h2 class="text-[13px] font-semibold">История торгов</h2>
              <span class="text-[10.5px] text-[#6B7280]">
                Строгость {{ detail.passport.auction_strictness_index.toFixed(2) }}
              </span>
            </div>

            <p v-if="detail.audit.history.length === 0" class="text-[11px] text-[#6B7280]">
              Архивные записи по данному кузову не найдены.
            </p>
            <ul v-else class="divide-y divide-[#F2F2F7] text-[10.5px]">
              <li
                v-for="record in detail.audit.history.slice(0, 3)"
                :key="`${record.auction_date}-${record.lot_number}`"
                class="flex items-center justify-between gap-2 py-1"
              >
                <div class="min-w-0">
                  <div class="truncate font-medium text-[#111827]">
                    {{ record.auction_date }} · {{ record.auction_house }} #{{ record.lot_number }}
                  </div>
                  <div v-if="record.defects_summary" class="truncate text-[10px] text-[#6B7280]">
                    {{ record.defects_summary }}
                  </div>
                </div>
                <div class="shrink-0 text-right font-medium tabular-nums">
                  <div>{{ record.overall_grade }}</div>
                  <div class="text-[10px] text-[#6B7280]">
                    {{ record.mileage_km !== null ? formatMileageKm(record.mileage_km) : '—' }}
                  </div>
                </div>
              </li>
            </ul>
          </div>

          <div class="mt-1.5 text-[10px] text-[#6B7280]">
            Источник кросс-аудита: {{ detail.audit.source_name }}
          </div>
        </div>
      </section>
    </div>

    <!-- PAGE 2: Body Defects Diagram (5 cols) + Defects, Notes, Farpost Repair (7 cols) + Cost Ladder -->
    <div class="break-before-page pt-[9mm] pb-[6mm]">
      <div class="flex items-center justify-between border-b border-[#E5E5EA] pb-2 text-[11px]">
        <span class="font-semibold text-[#111827]">
          {{ detail.passport.make }} {{ detail.passport.model }} · Лот #{{
            detail.passport.lot_number
          }}
        </span>
        <span class="text-[#6B7280]">Техническое состояние и калькуляция привоза</span>
      </div>

      <!-- Bento Row 4: Diagram (5 cols stretched) | Defects + Notes + Farpost Repair (7 cols stacked) -->
      <section class="mt-2.5 grid grid-cols-12 items-stretch gap-2.5">
        <div
          class="col-span-5 flex break-inside-avoid flex-col justify-between rounded-md border border-[#E5E5EA] bg-white p-3"
        >
          <div class="flex items-center justify-between">
            <h2 class="text-[13px] font-semibold">Схема дефектов</h2>
            <BaseBadge variant="neutral">{{ detail.passport.defects.length }} дефект(а)</BaseBadge>
          </div>

          <div class="my-auto py-1 [&_svg]:max-w-[154px]">
            <LotBodyDiagram :defects="detail.passport.defects" :selected-panel="null" />
          </div>

          <div v-if="riskChips.length > 0" class="flex flex-wrap gap-1 pt-1">
            <BaseBadge v-for="chip in riskChips" :key="chip.label" :variant="chip.variant">
              {{ chip.label }}
            </BaseBadge>
          </div>
        </div>

        <div class="col-span-7 flex flex-col gap-2.5">
          <div class="flex-1 break-inside-avoid rounded-md border border-[#E5E5EA] bg-white p-3">
            <h2 class="mb-1.5 text-[13px] font-semibold">Расшифровка дефектов</h2>
            <p v-if="detail.passport.defects.length === 0" class="text-[11px] text-[#6B7280]">
              Серьёзных дефектов кузова не отмечено.
            </p>
            <ul v-else class="space-y-1">
              <li
                v-for="defect in detail.passport.defects"
                :key="`${defect.panel_id}-${defect.raw_code}`"
                class="flex items-start justify-between gap-2 rounded-sm border border-[#E5E5EA] bg-[#F8F8FA] px-2.5 py-1.5"
              >
                <div class="min-w-0">
                  <div class="text-[11.5px] font-semibold">{{ defect.panel_ru }}</div>
                  <p class="text-[10.5px] leading-snug text-[#4B5563]">
                    {{ defect.description_ru }}
                  </p>
                </div>
                <BaseBadge :variant="getDefectTone(defect)" class="shrink-0 font-mono">
                  {{ defect.raw_code }}
                </BaseBadge>
              </li>
            </ul>
          </div>

          <div
            v-if="detail.passport.inspector_notes_ru.length > 0"
            class="break-inside-avoid rounded-md border border-[#E5E5EA] bg-white p-3"
          >
            <h2 class="mb-1 text-[12.5px] font-semibold">Замечания инспектора</h2>
            <ul class="list-disc space-y-0.5 pl-4 text-[10.5px] leading-snug text-[#374151]">
              <li v-for="note in detail.passport.inspector_notes_ru" :key="note">{{ note }}</li>
            </ul>
          </div>

          <div class="break-inside-avoid rounded-md border border-[#E5E5EA] bg-white p-3">
            <div class="mb-1 flex items-center justify-between gap-2">
              <h2 class="text-[13px] font-semibold">Смета ремонта Farpost</h2>
              <span class="text-[12.5px] font-semibold tabular-nums">
                {{ formatRub(repairTotalRub) }}
              </span>
            </div>

            <p v-if="repairTotalRub === 0" class="text-[11px] text-[#6B7280]">
              Кузовной ремонт и замена деталей не требуются.
            </p>
            <ul v-else class="divide-y divide-[#F2F2F7] text-[10.5px]">
              <li
                v-for="part in detail.economics.farpost_repair.parts"
                :key="`${part.panel_id}-${part.part_name_ru}`"
                class="flex items-center justify-between gap-2 py-0.5"
              >
                <span class="truncate">{{ part.part_name_ru }} ({{ part.defect_code }})</span>
                <span class="shrink-0 font-medium tabular-nums">
                  от {{ formatRub(part.price_from_rub) }}
                </span>
              </li>
              <li
                v-for="work in detail.economics.farpost_repair.service_works"
                :key="work.label_ru"
                class="flex items-center justify-between gap-2 py-0.5"
              >
                <span class="truncate">{{ work.label_ru }}</span>
                <span class="shrink-0 font-medium tabular-nums">
                  {{ formatRub(work.amount_rub) }}
                </span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <!-- Bento Row 5: Full Cost Ladder + Rates Snapshot -->
      <section
        class="mt-2.5 break-inside-avoid rounded-md border border-[#E5E5EA] bg-white p-3 [&_.p-4]:mt-2 [&_.p-4]:p-2.5 [&_li]:py-1 [&_li]:text-[12.5px]"
      >
        <div class="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 class="text-[14px] font-semibold">Себестоимость привоза во Владивосток под ключ</h2>
            <p class="text-[11px] text-[#6B7280]">
              Пошаговый расчёт от аукционной ставки до выдачи ЭПТС
            </p>
          </div>
          <div class="text-[11px] text-[#6B7280]">
            Курс валют: VL.ru Деньги · 1 ¥ =
            {{ detail.economics.customs.rates_snapshot.jpy_rub_bank.toFixed(3) }} ₽ · 1 € =
            {{ detail.economics.customs.rates_snapshot.eur_rub_cbrf.toFixed(2) }} ₽
          </div>
        </div>

        <CostLadder
          :steps="ladderSteps"
          total-label="Итого под ключ во Владивостоке"
          :total-value="formatRub(detail.economics.wise_cost_ladder.turnkey_cost_rub)"
        />
      </section>
    </div>
  </article>
</template>
