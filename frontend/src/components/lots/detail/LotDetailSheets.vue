<script setup lang="ts">
import { computed, type Component } from 'vue'

import LotAuditSheet from '@/components/lots/detail/sheets/LotAuditSheet.vue'
import LotInspectorNotesSheet from '@/components/lots/detail/sheets/LotInspectorNotesSheet.vue'
import LotRepairSheet from '@/components/lots/detail/sheets/LotRepairSheet.vue'
import LotSafetyChecklistSheet from '@/components/lots/detail/sheets/LotSafetyChecklistSheet.vue'
import LotScanSheet from '@/components/lots/detail/sheets/LotScanSheet.vue'
import type { LotDetailResponse } from '@/types/api'

export type LotDetailSheetKind = 'scan' | 'audit' | 'repair' | 'notes' | 'safety' | null

interface Props {
  detail: LotDetailResponse
}

defineProps<Props>()

const activeSheet = defineModel<LotDetailSheetKind>('activeSheet', { default: null })

const SHEET_COMPONENTS: Record<Exclude<LotDetailSheetKind, null>, Component> = {
  scan: LotScanSheet,
  audit: LotAuditSheet,
  repair: LotRepairSheet,
  notes: LotInspectorNotesSheet,
  safety: LotSafetyChecklistSheet,
}

const activeSheetComponent = computed(() =>
  activeSheet.value ? SHEET_COMPONENTS[activeSheet.value] : null,
)

const isCurrentSheetOpen = computed({
  get: () => activeSheet.value !== null,
  set: (open: boolean) => {
    if (!open) {
      activeSheet.value = null
    }
  },
})
</script>

<template>
  <component
    :is="activeSheetComponent"
    v-if="activeSheetComponent"
    v-model:open="isCurrentSheetOpen"
    :detail="detail"
  />
</template>
