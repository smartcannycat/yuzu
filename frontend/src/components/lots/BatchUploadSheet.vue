<script setup lang="ts">
import { AlertCircle } from '@lucide/vue'
import { computed, toRef } from 'vue'

import BatchStagedGrid from '@/components/lots/BatchStagedGrid.vue'
import BatchUploadDropzone from '@/components/lots/BatchUploadDropzone.vue'
import { useBatchUploadStaging } from '@/components/lots/composables/useBatchUploadStaging'
import { BaseButton, BottomSheet } from '@/components/ui'
import { BATCH_MAX_FILES_PER_UPLOAD } from '@/utils/batchFiles'
import { formatSheetCountRu } from '@/utils/formatters'

interface Props {
  mode?: 'create' | 'append'
  maxFiles?: number
  isSubmitting?: boolean
  serverError?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'create',
  maxFiles: BATCH_MAX_FILES_PER_UPLOAD,
  isSubmitting: false,
  serverError: null,
})

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  submit: [files: File[]]
}>()

const {
  stagedItems,
  isDragOver,
  validationError,
  isGeneratingDemo,
  effectiveMaxFiles,
  activeError,
  canAddMore,
  mascotBadgeText,
  submitLabel,
  clearStagedItems,
  addIncomingFiles,
  removeStagedItem,
  markItemImageFailed,
  addDemoSheets,
  handleDragEnter,
  handleDragOver,
  handleDragLeave,
  handleDrop,
} = useBatchUploadStaging({
  open,
  maxFiles: toRef(props, 'maxFiles'),
  isSubmitting: toRef(props, 'isSubmitting'),
  serverError: toRef(props, 'serverError'),
  mode: toRef(props, 'mode'),
})

const sheetTitle = computed(() =>
  props.mode === 'append' ? 'Догрузить ещё листы' : 'Загрузка аукционных листов',
)

const sheetSubtitle = computed(() =>
  props.mode === 'append'
    ? `Можно добавить ещё до ${formatSheetCountRu(effectiveMaxFiles.value)} в текущую очередь`
    : `Выберите от 1 до ${BATCH_MAX_FILES_PER_UPLOAD} фотографий бланков`,
)

function handleSubmit(): void {
  if (stagedItems.value.length === 0 || props.isSubmitting) return
  validationError.value = null
  emit(
    'submit',
    stagedItems.value.map((item) => item.file),
  )
}
</script>

<template>
  <BottomSheet
    v-model:open="open"
    :title="sheetTitle"
    :subtitle="sheetSubtitle"
    max-width="md"
    placement="center"
    :persistent="isSubmitting"
    :close-on-backdrop="!isSubmitting"
  >
    <div class="flex flex-col gap-4">
      <BatchUploadDropzone
        :has-selected-files="stagedItems.length > 0"
        :has-error="Boolean(activeError)"
        :is-drag-over="isDragOver"
        :can-add-more="canAddMore"
        :is-generating-demo="isGeneratingDemo"
        :mascot-badge-text="mascotBadgeText"
        @files-selected="addIncomingFiles"
        @add-demo="addDemoSheets"
        @drag-enter="handleDragEnter"
        @drag-over="handleDragOver"
        @drag-leave="handleDragLeave"
        @drop-files="handleDrop"
      />

      <div
        v-if="activeError"
        role="alert"
        class="bg-danger-bg text-danger flex items-start gap-2.5 rounded-md px-3.5 py-2.5 text-[13px] leading-snug"
      >
        <AlertCircle :size="16" :stroke-width="2" class="mt-0.5 shrink-0" />
        <p class="min-w-0 flex-1">{{ activeError }}</p>
      </div>

      <BatchStagedGrid
        :items="stagedItems"
        :max-files="effectiveMaxFiles"
        :is-submitting="isSubmitting"
        @clear-all="clearStagedItems"
        @remove-item="removeStagedItem"
        @image-error="markItemImageFailed"
      />
    </div>

    <template #footer>
      <div class="flex items-center gap-2.5">
        <div class="hidden sm:block">
          <BaseButton variant="secondary" :disabled="isSubmitting" @click="open = false">
            Отмена
          </BaseButton>
        </div>
        <BaseButton
          variant="primary"
          block
          :loading="isSubmitting"
          :disabled="stagedItems.length === 0 || isSubmitting"
          @click="handleSubmit"
        >
          {{ submitLabel }}
        </BaseButton>
      </div>
    </template>
  </BottomSheet>
</template>
