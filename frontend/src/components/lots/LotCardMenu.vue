<script setup lang="ts">
import { Archive, ArchiveRestore, Check, CheckSquare, MoreHorizontal, Trash2 } from '@lucide/vue'

import type { LotSummary } from '@/types/api'

interface Props {
  lot: LotSummary
  menuOpen: boolean
  selectionMode: boolean
  selected: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  toggleMenu: [lotId: string]
  closeMenu: []
  toggleArchive: [lot: LotSummary]
  deleteLot: [lot: LotSummary]
  startMultiSelect: [lot: LotSummary]
}>()

function handleArchiveAction(): void {
  emit('closeMenu')
  emit('toggleArchive', props.lot)
}

function handleMultiSelectAction(): void {
  emit('closeMenu')
  emit('startMultiSelect', props.lot)
}

function handleDeleteAction(): void {
  emit('closeMenu')
  emit('deleteLot', props.lot)
}
</script>

<template>
  <div data-lot-menu class="relative shrink-0">
    <span
      v-if="selectionMode"
      aria-hidden="true"
      class="inline-flex h-6 w-6 items-center justify-center rounded-full border transition-colors"
      :class="
        selected
          ? 'bg-accent border-accent text-text-on-accent'
          : 'bg-surface border-border-strong text-transparent'
      "
    >
      <Check :size="14" :stroke-width="2.5" />
    </span>

    <button
      v-else
      type="button"
      aria-label="Действия с лотом"
      :aria-expanded="menuOpen"
      aria-haspopup="menu"
      class="text-text-tertiary hover:text-text-primary hover:bg-surface-inset focus-visible:outline-accent -mt-1 -mr-1 inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full transition-colors focus-visible:outline-2"
      @click.stop="emit('toggleMenu', lot.lot_id)"
    >
      <MoreHorizontal :size="18" :stroke-width="2" />
    </button>

    <div
      v-if="menuOpen && !selectionMode"
      role="menu"
      aria-label="Действия с лотом"
      class="bg-surface border-border shadow-sheet absolute top-8 right-0 z-30 min-w-[196px] overflow-hidden rounded-md border py-1"
      @click.stop
    >
      <button
        type="button"
        role="menuitem"
        class="text-text-primary hover:bg-surface-hover flex w-full cursor-pointer items-center gap-2.5 px-3.5 py-2 text-left text-[13px] font-medium transition-colors"
        @click="handleArchiveAction"
      >
        <ArchiveRestore v-if="lot.is_archived" :size="15" :stroke-width="1.9" />
        <Archive v-else :size="15" :stroke-width="1.9" />
        <span>{{ lot.is_archived ? 'Вернуть в активные' : 'В архив' }}</span>
      </button>

      <button
        type="button"
        role="menuitem"
        class="text-text-primary hover:bg-surface-hover flex w-full cursor-pointer items-center gap-2.5 px-3.5 py-2 text-left text-[13px] font-medium transition-colors"
        @click="handleMultiSelectAction"
      >
        <CheckSquare :size="15" :stroke-width="1.9" />
        <span>Выбрать несколько</span>
      </button>

      <div class="border-border my-1 border-t" />

      <button
        type="button"
        role="menuitem"
        class="text-danger hover:bg-danger-bg flex w-full cursor-pointer items-center gap-2.5 px-3.5 py-2 text-left text-[13px] font-medium transition-colors"
        @click="handleDeleteAction"
      >
        <Trash2 :size="15" :stroke-width="1.9" />
        <span>Удалить</span>
      </button>
    </div>
  </div>
</template>
