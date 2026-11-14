<script setup lang="ts">
import { computed } from 'vue'

import LotBodyDiagram from '@/components/lots/detail/LotBodyDiagram.vue'
import { getDefectTone } from '@/components/lots/detail/lotDefects'
import {
  FX_RATE_SOURCE_LABEL,
  buildActiveRiskLabels,
  buildCostLadderSteps,
  resolveSafeJpyRate,
} from '@/components/lots/detail/lotPresentation'
import { BaseBadge, BrandLogo, CostLadder } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'
import type { DamagedPartItem } from '@/types/lots'
import { formatRub } from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
}

const props = defineProps<Props>()

const riskChips = computed(() => buildActiveRiskLabels(props.detail.passport.risk_flags))
const repairTotalRub = computed(() => props.detail.economics.farpost_repair.grand_total_repair_rub)
const jpyRate = computed(() =>
  resolveSafeJpyRate(props.detail.economics.customs.rates_snapshot.jpy_rub_bank),
)

const ladderSteps = computed(() => {
  const { economics } = props.detail
  return buildCostLadderSteps(economics.wise_cost_ladder.steps, {
    bidJpy: economics.wise_cost_ladder.car_bid_jpy,
    jpyRate: jpyRate.value,
    includeRepairs: economics.is_repairs_included,
  })
})

function partSourceLabel(part: DamagedPartItem): string {
  if (part.in_stock_vladivostok) {
    return part.subtitle_ru?.includes('в заводской цвет') ? 'Farpost, в цвет' : 'Farpost'
  }
  return part.subtitle_ru?.includes('из кэша') ? 'кэш Farpost' : 'оценка по матрице'
}
</script>

<template>
  <!-- PAGE 2: Body Defects Diagram (5 cols) + Defects, Notes, Farpost Repair (7 cols) + Cost Ladder -->
  <div class="break-before-page pt-[9mm] pb-[6mm]">
    <div class="flex items-center justify-between gap-4 border-b border-[#E5E5EA] pb-2">
      <div class="flex min-w-0 items-baseline gap-2 text-[11px]">
        <span class="font-semibold text-[#111827]">
          {{ detail.passport.make }} {{ detail.passport.model }} · Лот #{{
            detail.passport.lot_number
          }}
        </span>
        <span class="text-[#6B7280]">· Техническое состояние и калькуляция привоза</span>
      </div>
      <BrandLogo layout="report" :size="24" :animated="false" hide-subtitle class="shrink-0" />
    </div>

    <!-- Bento Row 4: Compact top grid (Body Diagram + Inspector Notes), never taller than 1 page -->
    <section class="mt-2.5 grid break-inside-avoid grid-cols-12 items-stretch gap-2.5">
      <div
        class="flex flex-col justify-between rounded-md border border-[#E5E5EA] bg-white p-3"
        :class="detail.passport.inspector_notes_ru.length > 0 ? 'col-span-5' : 'col-span-12'"
      >
        <div class="flex items-center justify-between gap-2">
          <h2 class="text-[13px] font-semibold">Схема дефектов</h2>
          <BaseBadge variant="neutral">{{ detail.passport.defects.length }} дефект(а)</BaseBadge>
        </div>

        <div class="my-auto py-1 [&_svg]:max-w-[154px]">
          <LotBodyDiagram :defects="detail.passport.defects" :selected-panel="null" />
        </div>

        <div v-if="riskChips.length > 0" class="flex flex-wrap gap-1 pt-1">
          <BaseBadge v-for="chip in riskChips" :key="chip.label" :variant="chip.variant" wrap>
            {{ chip.label }}
          </BaseBadge>
        </div>
      </div>

      <div
        v-if="detail.passport.inspector_notes_ru.length > 0"
        class="col-span-7 flex flex-col rounded-md border border-[#E5E5EA] bg-white p-3"
      >
        <h2 class="mb-1.5 text-[13px] font-semibold">Замечания инспектора</h2>
        <ul class="list-disc space-y-1 pl-4 text-[10.5px] leading-snug text-[#374151]">
          <li v-for="note in detail.passport.inspector_notes_ru" :key="note">{{ note }}</li>
        </ul>
      </div>
    </section>

    <!-- Bento Row 5: Defect Breakdown (flowable 2-col grid so long lists paginate cleanly) -->
    <section class="mt-2.5 rounded-md border border-[#E5E5EA] bg-white p-3">
      <div class="mb-1.5 flex break-after-avoid items-center justify-between gap-2">
        <h2 class="text-[13px] font-semibold">Расшифровка дефектов</h2>
        <span class="text-[11px] text-[#6B7280]">{{ detail.passport.defects.length }} поз.</span>
      </div>
      <p v-if="detail.passport.defects.length === 0" class="text-[11px] text-[#6B7280]">
        Серьёзных дефектов кузова не отмечено.
      </p>
      <ul v-else class="grid grid-cols-2 gap-1.5">
        <li
          v-for="defect in detail.passport.defects"
          :key="`${defect.panel_id}-${defect.raw_code}-${defect.description_ru}`"
          class="flex break-inside-avoid items-start justify-between gap-2 rounded-sm border border-[#E5E5EA] bg-[#F8F8FA] px-2 py-1"
        >
          <div class="min-w-0">
            <div class="text-[11px] font-semibold">{{ defect.panel_ru }}</div>
            <p class="text-[10px] leading-snug text-[#4B5563]">
              {{ defect.description_ru }}
            </p>
          </div>
          <BaseBadge :variant="getDefectTone(defect)" class="shrink-0 font-mono">
            {{ defect.raw_code }}
          </BaseBadge>
        </li>
      </ul>
    </section>

    <!-- Bento Row 6: Farpost Repair Estimate -->
    <section class="mt-2.5 break-inside-avoid rounded-md border border-[#E5E5EA] bg-white p-3">
      <div class="mb-1 flex break-after-avoid items-center justify-between gap-2">
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
          class="flex break-inside-avoid items-center justify-between gap-2 py-0.5"
        >
          <span class="truncate">
            {{ part.part_name_ru }} ({{ part.defect_code }})
            <span class="text-[#6B7280]">({{ partSourceLabel(part) }})</span>
          </span>
          <span class="shrink-0 font-medium tabular-nums">
            от {{ formatRub(part.price_from_rub) }}
          </span>
        </li>
        <li
          v-for="work in detail.economics.farpost_repair.service_works"
          :key="work.label_ru"
          class="flex break-inside-avoid items-center justify-between gap-2 py-0.5"
        >
          <span class="truncate">{{ work.label_ru }}</span>
          <span class="shrink-0 font-medium tabular-nums">
            {{ formatRub(work.amount_rub) }}
          </span>
        </li>
      </ul>
    </section>

    <!-- Bento Row 7: Full Cost Ladder + Rates Snapshot -->
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
          Курс валют: {{ FX_RATE_SOURCE_LABEL }} · 1 ¥ = {{ jpyRate.toFixed(3) }} ₽ · 1 € =
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
</template>
