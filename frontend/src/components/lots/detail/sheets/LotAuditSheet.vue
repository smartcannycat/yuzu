<script setup lang="ts">
import { BaseBadge, BaseButton, BottomSheet } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'
import { formatMileageKm } from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
}

defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })
</script>

<template>
  <BottomSheet
    v-model:open="open"
    title="История торгов и аудит"
    :subtitle="`${detail.audit.source_name} · ${detail.passport.frame_id}`"
    max-width="md"
  >
    <div class="flex flex-col gap-4">
      <div
        class="rounded-sm border p-3.5"
        :class="
          detail.audit.has_critical_anomaly
            ? 'border-danger/25 bg-danger-bg text-danger'
            : detail.audit.anomalies.length > 0
              ? 'border-warning/25 bg-warning-bg text-warning'
              : 'border-success/25 bg-success-bg text-success'
        "
      >
        <div class="text-[14px] font-semibold">
          {{ detail.audit.headline_ru }}
        </div>
        <div class="mt-1 text-[12px] opacity-85">
          Найдено выставлений в архиве: {{ detail.audit.times_auctioned }}
        </div>
      </div>

      <div v-if="detail.audit.anomalies.length > 0" class="flex flex-col gap-2.5">
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Выявленные нестыковки
        </h4>
        <div
          v-for="anomaly in detail.audit.anomalies"
          :key="anomaly.title_ru"
          class="border-border bg-surface rounded-sm border p-3"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-text-primary text-[14px] font-semibold">{{ anomaly.title_ru }}</span>
            <BaseBadge
              :variant="
                anomaly.severity === 'critical'
                  ? 'danger'
                  : anomaly.severity === 'warning'
                    ? 'warning'
                    : 'info'
              "
            >
              {{ anomaly.severity === 'critical' ? 'Критично' : 'Внимание' }}
            </BaseBadge>
          </div>
          <p class="text-text-secondary mt-1.5 text-[13px] leading-relaxed">
            {{ anomaly.message_ru }}
          </p>

          <div
            v-if="anomaly.diff_details"
            class="bg-surface-inset mt-2.5 grid grid-cols-1 gap-1.5 rounded-xs p-2.5 text-[12px] sm:grid-cols-2"
          >
            <div
              v-for="(val, key) in anomaly.diff_details"
              :key="key"
              class="flex justify-between gap-2"
            >
              <span class="text-text-secondary">{{ String(key) }}:</span>
              <span class="text-text-primary font-medium">{{ String(val ?? '—') }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="detail.audit.history.length > 0" class="flex flex-col gap-2.5">
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Хронология торгов в Японии
        </h4>

        <ol class="flex flex-col gap-2.5">
          <li
            v-for="record in detail.audit.history"
            :key="`${record.auction_date}-${record.lot_number}`"
            class="border-border bg-surface-inset/50 rounded-sm border p-3"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="text-text-primary text-[14px] font-semibold">
                {{ record.auction_date }} · {{ record.auction_house }} #{{ record.lot_number }}
              </div>
              <BaseBadge :variant="record.overall_grade === 'R' ? 'danger' : 'neutral'">
                Оценка {{ record.overall_grade }}
              </BaseBadge>
            </div>

            <div class="text-text-secondary mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[12px]">
              <span>Пробег: {{ formatMileageKm(record.mileage_km) }}</span>
              <span v-if="record.closing_price_jpy">
                Цена: {{ record.closing_price_jpy.toLocaleString('ru-RU') }} ¥
              </span>
            </div>

            <p
              v-if="record.defects_summary"
              class="text-text-primary mt-1.5 text-[12px] leading-snug"
            >
              {{ record.defects_summary }}
            </p>
          </li>
        </ol>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="open = false">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
