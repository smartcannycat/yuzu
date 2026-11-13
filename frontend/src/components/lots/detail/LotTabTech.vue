<script setup lang="ts">
import { CheckCircle2, FileText, ShieldAlert, ShieldCheck, Wrench } from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import LotBodyDiagram from '@/components/lots/detail/LotBodyDiagram.vue'
import { getDefectTone } from '@/components/lots/detail/lotDefects'
import { buildActiveRiskLabels } from '@/components/lots/detail/lotPresentation'
import { BaseBadge, BaseCard, InsetListGroup, InsetListItem } from '@/components/ui'
import type { BodyPanel, LotDetailResponse } from '@/types/api'
import { formatRub } from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  openRepair: []
  openInspectorNotes: []
  openSafetyChecklist: []
}>()

const selectedPanel = ref<BodyPanel | null>(null)

watch(
  () => props.detail.lot_id,
  () => {
    selectedPanel.value = null
  },
)

const repairValueText = computed(() => {
  const total = props.detail.economics.farpost_repair.grand_total_repair_rub
  return total > 0 ? formatRub(total) : '0 ₽'
})

const notesSubtitle = computed(() => {
  const count = props.detail.passport.inspector_notes_ru.length
  return count > 0 ? `${count} переведённых заметок` : 'Без дополнительных замечаний'
})

const safetySquircleColor = computed(() => {
  const status = props.detail.safety_checklist.overall_status
  if (status === 'critical') return '#FF3B30'
  if (status === 'warning') return '#FF9500'
  return '#34C759'
})

const activeRiskLabels = computed(() => buildActiveRiskLabels(props.detail.passport.risk_flags))

function toggleDefectRow(panelId: BodyPanel): void {
  selectedPanel.value = selectedPanel.value === panelId ? null : panelId
}
</script>

<template>
  <div class="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:items-start lg:gap-5">
    <!-- Left Column: Compact 2D Schematic -->
    <BaseCard variant="surface" padding="md" class="min-w-0 lg:col-span-5">
      <div class="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="text-text-primary text-[16px] font-semibold">Схема дефектов кузова</h2>
          <p class="text-text-secondary text-[12px]">Нажмите на пин, чтобы выделить панель</p>
        </div>
        <BaseBadge variant="neutral">{{ detail.passport.defects.length }} дефект(а)</BaseBadge>
      </div>

      <div class="bg-surface-inset/50 border-border rounded-sm border px-3 py-3">
        <LotBodyDiagram v-model:selected-panel="selectedPanel" :defects="detail.passport.defects" />
      </div>
    </BaseCard>

    <!-- Right Column: Defect Breakdown + Drilldown Rows + Risk Badges -->
    <div class="flex min-w-0 flex-col gap-4 lg:col-span-7">
      <!-- Defect Explanations Card -->
      <BaseCard variant="surface" padding="md">
        <div class="mb-2.5 flex items-center justify-between gap-2">
          <h3 class="text-text-primary text-[15px] font-semibold">Расшифровка дефектов</h3>
          <span v-if="detail.passport.defects.length > 0" class="text-text-secondary text-[12px]">
            Нажмите на строку для подсветки
          </span>
        </div>

        <ul
          v-if="detail.passport.defects.length > 0"
          class="flex flex-col gap-2 lg:max-h-[280px] lg:overflow-y-auto lg:pr-0.5"
        >
          <li
            v-for="(defect, index) in detail.passport.defects"
            :key="`${defect.panel_id}-${defect.raw_code}-${index}`"
          >
            <button
              type="button"
              class="flex w-full cursor-pointer items-start justify-between gap-3 rounded-sm border px-3 py-2 text-left transition-colors"
              :class="
                selectedPanel === defect.panel_id
                  ? 'border-accent bg-accent-subtle/60'
                  : 'border-border bg-surface hover:bg-surface-hover/70'
              "
              @click="toggleDefectRow(defect.panel_id)"
            >
              <div class="min-w-0">
                <div class="text-text-primary text-[14px] font-medium">
                  {{ defect.panel_ru }}
                </div>
                <p class="text-text-secondary mt-0.5 text-[12px] leading-snug">
                  {{ defect.description_ru }}
                </p>
              </div>
              <BaseBadge :variant="getDefectTone(defect)" class="shrink-0 font-mono">
                {{ defect.raw_code }}
              </BaseBadge>
            </button>
          </li>
        </ul>

        <div
          v-else
          class="bg-success-bg text-success flex items-center gap-2 rounded-sm px-3.5 py-2.5 text-[13px] font-medium"
        >
          <CheckCircle2 :size="16" class="shrink-0" />
          <span>На схеме аукционного листа значимых дефектов кузова не отмечено</span>
        </div>
      </BaseCard>

      <InsetListGroup title="Диагностика и смета">
        <InsetListItem
          title="Смета ремонта Farpost"
          :subtitle="
            detail.economics.farpost_repair.has_color_matched_parts
              ? 'Деталь подобрана в заводской цвет'
              : 'Оценка запчастей и работ во Владивостоке'
          "
          :value="repairValueText"
          squircle-color="#AF52DE"
          interactive
          chevron
          @click="emit('openRepair')"
        >
          <template #icon>
            <Wrench :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>

        <InsetListItem
          title="Замечания инспектора аукциона"
          :subtitle="notesSubtitle"
          value="Перевод"
          squircle-color="#007AFF"
          interactive
          chevron
          @click="emit('openInspectorNotes')"
        >
          <template #icon>
            <FileText :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>

        <InsetListItem
          title="Системы безопасности"
          subtitle="Силовой каркас, SRS, днище и следы воды"
          :value="detail.safety_checklist.overall_label_ru"
          :squircle-color="safetySquircleColor"
          interactive
          chevron
          @click="emit('openSafetyChecklist')"
        >
          <template #icon>
            <ShieldAlert
              v-if="detail.safety_checklist.overall_status !== 'ok'"
              :size="16"
              :stroke-width="2"
            />
            <ShieldCheck v-else :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>
      </InsetListGroup>

      <BaseCard v-if="activeRiskLabels.length > 0" variant="surface" padding="md">
        <div
          class="text-text-secondary mb-2.5 text-[12px] font-semibold tracking-[0.04em] uppercase"
        >
          Флаги осмотра
        </div>
        <div class="flex flex-wrap gap-1.5">
          <BaseBadge v-for="chip in activeRiskLabels" :key="chip.label" :variant="chip.variant">
            {{ chip.label }}
          </BaseBadge>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
