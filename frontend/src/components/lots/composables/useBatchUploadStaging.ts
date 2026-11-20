import { computed, onScopeDispose, ref, watch, type Ref } from 'vue'

import { isMockMode } from '@/api'
import {
  BATCH_MAX_FILES_PER_UPLOAD,
  isHeicFile,
  validateBatchFileAddition,
} from '@/utils/batchFiles'
import { extractApiErrorMessage } from '@/utils/errors'
import { formatSheetCountRu } from '@/utils/formatters'

export interface StagedSheetItem {
  id: string
  file: File
  previewUrl: string | null
  isHeic: boolean
  imageFailed: boolean
}

export interface UseBatchUploadStagingOptions {
  open: Ref<boolean>
  maxFiles: Ref<number>
  isSubmitting: Ref<boolean>
  serverError: Ref<string | null>
  mode: Ref<'create' | 'append'>
}

export function useBatchUploadStaging(options: UseBatchUploadStagingOptions) {
  const stagedItems = ref<StagedSheetItem[]>([])
  const isDragOver = ref(false)
  const validationError = ref<string | null>(null)
  const isGeneratingDemo = ref(false)

  let dragEnterDepth = 0
  let addSequence = 0
  let itemKeyCounter = 0

  function createStagedItemId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
    itemKeyCounter += 1
    return `staged-${itemKeyCounter}`
  }

  const effectiveMaxFiles = computed(() =>
    Math.max(0, Math.min(BATCH_MAX_FILES_PER_UPLOAD, options.maxFiles.value)),
  )

  const activeError = computed(() => validationError.value || options.serverError.value || null)

  const canAddMore = computed(
    () => stagedItems.value.length < effectiveMaxFiles.value && !options.isSubmitting.value,
  )

  const mascotBadgeText = computed(() => {
    if (activeError.value) {
      return 'Нужно поправить выбор файлов'
    }
    if (isDragOver.value) {
      return 'Отпустите фото, чтобы добавить в пачку'
    }
    if (stagedItems.value.length > 0) {
      return `Готово к запуску: ${formatSheetCountRu(stagedItems.value.length)}`
    }
    return 'JPG, PNG, WEBP или HEIC до 15 МБ'
  })

  const submitLabel = computed(() => {
    if (stagedItems.value.length === 0) {
      return options.mode.value === 'append' ? 'Выберите листы' : 'Запустить расчёт'
    }
    const countLabel = formatSheetCountRu(stagedItems.value.length)
    return options.mode.value === 'append'
      ? `Догрузить (${countLabel})`
      : `Запустить расчёт (${countLabel})`
  })

  function revokeItemPreview(item: StagedSheetItem): void {
    if (
      item.previewUrl &&
      typeof URL !== 'undefined' &&
      typeof URL.revokeObjectURL === 'function'
    ) {
      URL.revokeObjectURL(item.previewUrl)
    }
  }

  function clearStagedItems(): void {
    addSequence += 1
    for (const item of stagedItems.value) {
      revokeItemPreview(item)
    }
    stagedItems.value = []
    validationError.value = null
    isDragOver.value = false
    dragEnterDepth = 0
  }

  watch(options.open, (isOpen) => {
    if (!isOpen) {
      clearStagedItems()
    } else {
      validationError.value = null
    }
  })

  onScopeDispose(() => {
    clearStagedItems()
  })

  function buildStagedItem(file: File): StagedSheetItem {
    const heic = isHeicFile(file)
    let previewUrl: string | null = null
    if (!heic && typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
      try {
        previewUrl = URL.createObjectURL(file)
      } catch {
        previewUrl = null
      }
    }

    return {
      id: createStagedItemId(),
      file,
      previewUrl,
      isHeic: heic,
      imageFailed: false,
    }
  }

  async function addIncomingFiles(incoming: readonly File[]): Promise<void> {
    if (options.isSubmitting.value || incoming.length === 0) return

    const seq = ++addSequence
    const currentFiles = stagedItems.value.map((item) => item.file)

    try {
      const result = await validateBatchFileAddition(
        currentFiles,
        incoming,
        effectiveMaxFiles.value,
      )
      if (seq !== addSequence || !options.open.value || options.isSubmitting.value) return

      if (!result.ok) {
        validationError.value = result.error
        return
      }

      validationError.value = null
      const nextItems = result.files.map(buildStagedItem)
      stagedItems.value = [...stagedItems.value, ...nextItems]
    } catch (error: unknown) {
      if (seq !== addSequence || !options.open.value) return
      validationError.value = extractApiErrorMessage(error, 'Не удалось прочитать выбранные файлы.')
    }
  }

  function removeStagedItem(id: string): void {
    if (options.isSubmitting.value) return
    const target = stagedItems.value.find((item) => item.id === id)
    if (target) {
      revokeItemPreview(target)
    }
    stagedItems.value = stagedItems.value.filter((item) => item.id !== id)
    validationError.value = null
  }

  function markItemImageFailed(id: string): void {
    stagedItems.value = stagedItems.value.map((item) =>
      item.id === id ? { ...item, imageFailed: true } : item,
    )
  }

  async function addDemoSheets(): Promise<void> {
    if (!isMockMode || !canAddMore.value || isGeneratingDemo.value) return
    isGeneratingDemo.value = true
    try {
      const remaining = effectiveMaxFiles.value - stagedItems.value.length
      const { createDemoAuctionSheetFiles } = await import('@/utils/batchDemo')
      const demoFiles = await createDemoAuctionSheetFiles(remaining)
      if (demoFiles.length > 0) {
        await addIncomingFiles(demoFiles)
      }
    } catch (error: unknown) {
      validationError.value = extractApiErrorMessage(error, 'Не удалось подготовить демо-листы.')
    } finally {
      isGeneratingDemo.value = false
    }
  }

  function handleDragEnter(event: DragEvent): void {
    if (options.isSubmitting.value) return
    if (!event.dataTransfer?.types?.includes('Files')) return
    dragEnterDepth += 1
    isDragOver.value = true
  }

  function handleDragOver(event: DragEvent): void {
    if (options.isSubmitting.value) return
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = canAddMore.value ? 'copy' : 'none'
    }
  }

  function handleDragLeave(): void {
    dragEnterDepth = Math.max(0, dragEnterDepth - 1)
    if (dragEnterDepth === 0) {
      isDragOver.value = false
    }
  }

  function handleDrop(event: DragEvent): void {
    dragEnterDepth = 0
    isDragOver.value = false
    if (options.isSubmitting.value) return
    const droppedFiles = event.dataTransfer?.files ? Array.from(event.dataTransfer.files) : []
    if (droppedFiles.length === 0) return
    void addIncomingFiles(droppedFiles)
  }

  return {
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
  }
}
