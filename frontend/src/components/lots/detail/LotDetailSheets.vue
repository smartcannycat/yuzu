<script setup lang="ts">
import { AlertTriangle, CheckCircle2, OctagonAlert, ZoomIn, ZoomOut } from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import { BaseBadge, BaseButton, BottomSheet } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'
import { formatMileageKm, formatRub } from '@/utils/formatters'

export type LotDetailSheetKind = 'scan' | 'audit' | 'repair' | 'notes' | 'safety' | null

interface Props {
  detail: LotDetailResponse
}

const props = defineProps<Props>()

const activeSheet = defineModel<LotDetailSheetKind>('activeSheet', { default: null })

const zoomPercent = ref<100 | 150 | 200>(100)

watch(activeSheet, (next) => {
  if (next === 'scan') {
    zoomPercent.value = 100
  }
})

function bindSheetOpen(kind: Exclude<LotDetailSheetKind, null>) {
  return computed({
    get: () => activeSheet.value === kind,
    set: (open: boolean) => {
      if (!open && activeSheet.value === kind) {
        activeSheet.value = null
      }
    },
  })
}

const isScanOpen = bindSheetOpen('scan')
const isAuditOpen = bindSheetOpen('audit')
const isRepairOpen = bindSheetOpen('repair')
const isNotesOpen = bindSheetOpen('notes')
const isSafetyOpen = bindSheetOpen('safety')

function cycleZoom(): void {
  zoomPercent.value = zoomPercent.value === 100 ? 150 : zoomPercent.value === 150 ? 200 : 100
}
</script>

<template>
  <!-- 1. Original Auction Sheet Lightbox -->
  <BottomSheet
    v-model:open="isScanOpen"
    title="Оригинальный аукционный лист"
    :subtitle="`${detail.passport.auction_house} #${detail.passport.lot_number} · ${detail.passport.frame_id}`"
    max-width="lg"
  >
    <div class="flex flex-col gap-3">
      <div class="flex items-center justify-between gap-2">
        <span class="text-text-secondary text-[12px]"> Масштаб просмотра: {{ zoomPercent }}% </span>
        <BaseButton variant="secondary" size="sm" pill @click="cycleZoom">
          <template #icon-left>
            <ZoomOut v-if="zoomPercent === 200" :size="14" />
            <ZoomIn v-else :size="14" />
          </template>
          {{ zoomPercent === 200 ? 'Сбросить масштаб' : 'Увеличить' }}
        </BaseButton>
      </div>

      <div class="border-border bg-surface-inset max-h-[64vh] overflow-auto rounded-sm border p-2">
        <img
          :src="detail.media.sheet_scan_url"
          :alt="`Аукционный лист ${detail.passport.make} ${detail.passport.model} #${detail.passport.lot_number}`"
          class="mx-auto block rounded-xs transition-all duration-150"
          :style="{ width: `${zoomPercent}%`, maxWidth: 'none' }"
        />
      </div>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="activeSheet = null">Закрыть</BaseButton>
    </template>
  </BottomSheet>

  <!-- 2. Cross-Audit & Japanese Auction History -->
  <BottomSheet
    v-model:open="isAuditOpen"
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
      <BaseButton variant="primary" block @click="activeSheet = null">Закрыть</BaseButton>
    </template>
  </BottomSheet>

  <!-- 3. Farpost Repair Estimate -->
  <BottomSheet
    v-model:open="isRepairOpen"
    title="Смета ремонта Farpost"
    :subtitle="`Итого: ${formatRub(detail.economics.farpost_repair.grand_total_repair_rub)}`"
    max-width="md"
  >
    <div class="flex flex-col gap-4">
      <div v-if="detail.economics.farpost_repair.parts.length > 0" class="flex flex-col gap-2">
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Кузовные и контрактные детали
        </h4>
        <div
          v-for="part in detail.economics.farpost_repair.parts"
          :key="`${part.panel_id}-${part.defect_code}`"
          class="border-border bg-surface rounded-sm border p-3"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-text-primary text-[14px] font-medium">{{ part.part_name_ru }}</div>
              <p v-if="part.subtitle_ru" class="text-text-secondary mt-0.5 text-[12px]">
                {{ part.subtitle_ru }}
              </p>
            </div>
            <span class="text-text-primary shrink-0 text-[14px] font-semibold tabular-nums">
              от {{ formatRub(part.price_from_rub) }}
            </span>
          </div>

          <div class="mt-2 flex flex-wrap gap-1.5">
            <BaseBadge :variant="part.in_stock_vladivostok ? 'success' : 'warning'">
              {{
                part.in_stock_vladivostok ? 'В наличии во Владивостоке' : 'Под подбор / статистика'
              }}
            </BaseBadge>
            <BaseBadge variant="neutral">Код {{ part.defect_code }}</BaseBadge>
          </div>
        </div>
      </div>

      <div
        v-if="detail.economics.farpost_repair.service_works.length > 0"
        class="flex flex-col gap-2"
      >
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Работы СТО и покраска
        </h4>
        <div
          v-for="work in detail.economics.farpost_repair.service_works"
          :key="work.label_ru"
          class="border-border bg-surface-inset/50 flex items-start justify-between gap-3 rounded-sm border p-3"
        >
          <div class="min-w-0">
            <div class="text-text-primary text-[13px] font-medium">{{ work.label_ru }}</div>
            <div v-if="work.zero_cost_reason_ru" class="text-success mt-0.5 text-[12px]">
              {{ work.zero_cost_reason_ru }}
            </div>
          </div>
          <span class="text-text-primary shrink-0 text-[14px] font-semibold tabular-nums">
            {{ formatRub(work.amount_rub) }}
          </span>
        </div>
      </div>

      <div
        v-if="
          detail.economics.farpost_repair.parts.length === 0 &&
          detail.economics.farpost_repair.service_works.length === 0
        "
        class="bg-success-bg text-success rounded-sm p-3.5 text-[13px]"
      >
        Существенных кузовных повреждений под ремонт не выявлено.
      </div>

      <div class="bg-surface-inset text-text-secondary rounded-sm px-3.5 py-2.5 text-[12px]">
        {{ detail.economics.farpost_repair.included_in_turnkey_hint_ru }}
      </div>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="activeSheet = null">Закрыть</BaseButton>
    </template>
  </BottomSheet>

  <!-- 4. Inspector Notes & Japanese Raw -->
  <BottomSheet
    v-model:open="isNotesOpen"
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
      <BaseButton variant="primary" block @click="activeSheet = null">Закрыть</BaseButton>
    </template>
  </BottomSheet>

  <!-- 5. Safety Checklist -->
  <BottomSheet
    v-model:open="isSafetyOpen"
    title="Системы безопасности"
    :subtitle="`Итоговый статус: ${detail.safety_checklist.overall_label_ru}`"
    max-width="md"
  >
    <ul class="flex flex-col gap-2.5">
      <li
        v-for="item in detail.safety_checklist.items"
        :key="item.system_key"
        class="border-border bg-surface flex items-start gap-3 rounded-sm border p-3"
      >
        <CheckCircle2 v-if="item.status === 'ok'" :size="18" class="text-success mt-0.5 shrink-0" />
        <AlertTriangle
          v-else-if="item.status === 'warning'"
          :size="18"
          class="text-warning mt-0.5 shrink-0"
        />
        <OctagonAlert v-else :size="18" class="text-danger mt-0.5 shrink-0" />

        <div class="min-w-0 flex-1">
          <div class="text-text-primary text-[14px] font-semibold">{{ item.label_ru }}</div>
          <p class="text-text-secondary mt-0.5 text-[13px] leading-snug">{{ item.detail_ru }}</p>
        </div>
      </li>
    </ul>

    <template #footer>
      <BaseButton variant="primary" block @click="activeSheet = null">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
