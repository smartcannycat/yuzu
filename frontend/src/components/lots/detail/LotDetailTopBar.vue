<script setup lang="ts">
import { Archive, ArchiveRestore, ArrowLeft, Printer, RotateCcw, Trash2 } from '@lucide/vue'

import { BaseButton } from '@/components/ui'

interface Props {
  hasDetail: boolean
  isArchived: boolean
  isSimulationModified: boolean
  isRecalculating: boolean
  isUpdatingLifecycle: boolean
  isDeletingLot: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  back: []
  resetSimulation: []
  toggleArchive: []
  openDelete: []
  printPdf: []
}>()
</script>

<template>
  <header class="flex flex-wrap items-center justify-between gap-3">
    <button
      type="button"
      class="text-text-secondary hover:text-text-primary hover:bg-surface inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[14px] font-medium whitespace-nowrap transition-colors"
      @click="emit('back')"
    >
      <ArrowLeft :size="17" :stroke-width="2" />
      <span>Назад</span>
    </button>

    <div v-if="hasDetail" class="flex flex-wrap items-center gap-2">
      <BaseButton
        v-if="isSimulationModified"
        variant="ghost"
        size="sm"
        pill
        :disabled="isRecalculating"
        @click="emit('resetSimulation')"
      >
        <template #icon-left>
          <RotateCcw :size="14" />
        </template>
        Сбросить ставку
      </BaseButton>

      <BaseButton
        variant="secondary"
        size="sm"
        pill
        :loading="isUpdatingLifecycle"
        :disabled="isDeletingLot"
        @click="emit('toggleArchive')"
      >
        <template #icon-left>
          <ArchiveRestore v-if="isArchived" :size="15" />
          <Archive v-else :size="15" />
        </template>
        {{ isArchived ? 'Из архива' : 'В архив' }}
      </BaseButton>

      <BaseButton
        variant="secondary"
        size="sm"
        pill
        :disabled="isUpdatingLifecycle || isDeletingLot"
        class="!text-danger hover:!border-danger/30 hover:!bg-danger-subtle"
        @click="emit('openDelete')"
      >
        <template #icon-left>
          <Trash2 :size="15" />
        </template>
        Удалить
      </BaseButton>

      <BaseButton variant="secondary" size="sm" pill @click="emit('printPdf')">
        <template #icon-left>
          <Printer :size="15" />
        </template>
        PDF
      </BaseButton>
    </div>
  </header>
</template>
