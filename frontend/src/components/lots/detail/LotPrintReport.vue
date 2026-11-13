<script setup lang="ts">
import type { LotDetailResponse } from '@/types/api'
import {
  cleanVerdictText,
  formatEngineLiters,
  formatMileageKm,
  formatRub,
} from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
  isSimulationModified?: boolean
}

defineProps<Props>()
</script>

<template>
  <section class="hidden bg-white p-6 text-[#111827] print:block">
    <header class="border-b border-[#D1D1D6] pb-4">
      <div class="text-[11px] font-semibold tracking-[0.06em] text-[#6B7280] uppercase">
        YUZU Report: Экспертное заключение дефектоскопии и себестоимости
      </div>
      <div class="mt-1 flex items-baseline justify-between gap-4">
        <h1 class="text-[22px] font-semibold">
          {{ detail.passport.make }} {{ detail.passport.model }}
          <span v-if="detail.passport.trim" class="font-normal text-[#4B5563]">
            {{ detail.passport.trim }}
          </span>
        </h1>
        <span class="text-[13px] font-medium text-[#4B5563]">
          {{ detail.passport.auction_house }} #{{ detail.passport.lot_number }} ·
          {{ detail.passport.frame_id }}
        </span>
      </div>
      <div class="mt-1 text-[12px] text-[#6B7280]">
        {{ detail.passport.first_reg_year ?? '—' }} ·
        {{ formatEngineLiters(detail.passport.engine_cc) }} ·
        {{ formatMileageKm(detail.passport.mileage_km) }} · Оценка
        {{ detail.passport.overall_grade }}
        <span v-if="isSimulationModified"> · Параметры ставки скорректированы вручную</span>
      </div>
    </header>

    <div class="mt-4 rounded-sm border border-[#E5E5EA] bg-[#F8F8FA] p-4">
      <div class="text-[14px] font-semibold">
        {{ cleanVerdictText(detail.verdict.headline) }}
      </div>
      <div class="mt-1 text-[13px] text-[#374151]">
        Под ключ во Владивостоке:
        <strong>{{ formatRub(detail.economics.wise_cost_ladder.turnkey_cost_rub) }}</strong>
        · Рынок РФ (Drom):
        <strong>{{ formatRub(detail.market.market_price_rf_rub) }}</strong>
        · {{ detail.verdict.badge_text }}
      </div>
      <div class="mt-2 text-[12px] text-[#4B5563]">
        <div>Кузов: {{ detail.verdict.body_summary_ru }}</div>
        <div>Салон: {{ detail.verdict.interior_summary_ru }}</div>
      </div>
    </div>

    <div class="mt-4">
      <h2 class="mb-2 text-[14px] font-semibold">Лестница себестоимости</h2>
      <table class="w-full border-collapse text-[12px]">
        <tbody>
          <tr
            v-for="step in detail.economics.wise_cost_ladder.steps"
            :key="step.step_number"
            class="border-b border-[#E5E5EA]"
          >
            <td class="py-1.5 pr-3">{{ step.step_number }}. {{ step.name_ru }}</td>
            <td class="py-1.5 text-right font-semibold tabular-nums">
              {{ formatRub(step.amount_rub) }}
            </td>
          </tr>
          <tr>
            <td class="pt-2 font-semibold">Итого под ключ</td>
            <td class="pt-2 text-right text-[14px] font-semibold tabular-nums">
              {{ formatRub(detail.economics.wise_cost_ladder.turnkey_cost_rub) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="detail.passport.defects.length > 0" class="mt-4">
      <h2 class="mb-1.5 text-[14px] font-semibold">Отмеченные дефекты кузова</h2>
      <ul class="list-disc space-y-1 pl-4 text-[12px] text-[#374151]">
        <li
          v-for="defect in detail.passport.defects"
          :key="`${defect.panel_id}-${defect.raw_code}`"
        >
          <strong>{{ defect.raw_code }}</strong> — {{ defect.description_ru }}
        </li>
      </ul>
    </div>
  </section>
</template>
