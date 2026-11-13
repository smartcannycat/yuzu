<script setup lang="ts">
import { computed } from 'vue'

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
</script>

<template>
  <LotScanSheet v-model:open="isScanOpen" :detail="detail" />
  <LotAuditSheet v-model:open="isAuditOpen" :detail="detail" />
  <LotRepairSheet v-model:open="isRepairOpen" :detail="detail" />
  <LotInspectorNotesSheet v-model:open="isNotesOpen" :detail="detail" />
  <LotSafetyChecklistSheet v-model:open="isSafetyOpen" :detail="detail" />
</template>
