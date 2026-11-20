<script setup lang="ts">
import { CheckSquare, Trash2, Undo2 } from '@lucide/vue'

import { BaseButton } from '@/components/ui'
import type { LotSummary } from '@/types/api'

interface Props {
  pendingDeleteLot: LotSummary | null
  selectionMode: boolean
  selectedCount: number
  allVisibleSelected: boolean
  isBulkDeleting: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  undoDelete: []
  toggleSelectAll: []
  cancelSelection: []
  bulkDelete: []
}>()
</script>

<template>
  <!-- Single-delete 5-second Undo Toast -->
  <div
    v-if="pendingDeleteLot && !selectionMode"
    role="status"
    aria-live="polite"
    class="bg-text-primary text-surface fixed inset-x-4 bottom-5 z-40 mx-auto flex max-w-md items-center justify-between gap-3 rounded-full px-4 py-2.5 shadow-xl sm:inset-x-auto sm:left-1/2 sm:min-w-[360px] sm:-translate-x-1/2"
  >
    <span class="truncate text-[13px] font-medium">
      «{{ pendingDeleteLot.make }} {{ pendingDeleteLot.model }}» удалён
    </span>
    <button
      type="button"
      class="text-accent hover:text-accent/90 inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-semibold transition-colors"
      @click="emit('undoDelete')"
    >
      <Undo2 :size="14" />
      <span>Отменить</span>
    </button>
  </div>

  <!-- Bulk Selection Floating Bar -->
  <div
    v-if="selectionMode"
    role="region"
    aria-label="Массовые действия с лотами"
    class="bg-surface border-border fixed inset-x-3 bottom-4 z-40 mx-auto flex max-w-2xl flex-wrap items-center justify-between gap-2 rounded-2xl border px-3.5 py-2.5 shadow-xl sm:inset-x-auto sm:bottom-5 sm:left-1/2 sm:w-full sm:-translate-x-1/2 sm:rounded-full sm:px-4"
  >
    <div class="flex items-center gap-2.5">
      <CheckSquare :size="16" class="text-accent shrink-0" />
      <span class="text-text-primary text-[13px] font-semibold tabular-nums">
        Выбрано: {{ selectedCount }}
      </span>
      <button
        type="button"
        class="text-accent hover:text-accent-hover cursor-pointer text-[13px] font-medium"
        @click="emit('toggleSelectAll')"
      >
        {{ allVisibleSelected ? 'Снять все' : 'Выбрать все' }}
      </button>
    </div>

    <div class="flex items-center gap-2">
      <BaseButton
        variant="ghost"
        size="sm"
        pill
        :disabled="isBulkDeleting"
        @click="emit('cancelSelection')"
      >
        Отмена
      </BaseButton>
      <BaseButton
        variant="destructive"
        size="sm"
        pill
        :disabled="selectedCount === 0"
        :loading="isBulkDeleting"
        @click="emit('bulkDelete')"
      >
        <template #icon-left>
          <Trash2 :size="14" />
        </template>
        Удалить ({{ selectedCount }})
      </BaseButton>
    </div>
  </div>
</template>
