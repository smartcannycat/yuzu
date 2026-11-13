<script setup lang="ts">
import { AlertCircle, Camera, Check, FileImage, ImagePlus, Sparkles, Upload, X } from '@lucide/vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { isMockMode } from '@/api'
import { CapyMascot } from '@/components/mascot'
import { BaseButton, BottomSheet } from '@/components/ui'
import {
  BATCH_ACCEPT_ATTR,
  BATCH_MAX_FILES_PER_UPLOAD,
  formatFileSizeRu,
  isHeicFile,
  validateBatchFileAddition,
} from '@/utils/batchFiles'
import { formatSheetCountRu } from '@/utils/formatters'

interface StagedSheetItem {
  id: string
  file: File
  previewUrl: string | null
  isHeic: boolean
  imageFailed: boolean
}

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

const galleryInputRef = ref<HTMLInputElement | null>(null)
const cameraInputRef = ref<HTMLInputElement | null>(null)
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
  Math.max(0, Math.min(BATCH_MAX_FILES_PER_UPLOAD, props.maxFiles)),
)

const activeError = computed(() => validationError.value || props.serverError || null)

const sheetTitle = computed(() =>
  props.mode === 'append' ? 'Догрузить ещё листы' : 'Загрузка аукционных листов',
)

const sheetSubtitle = computed(() =>
  props.mode === 'append'
    ? `Можно добавить ещё до ${formatSheetCountRu(effectiveMaxFiles.value)} в текущую очередь`
    : `Выберите от 1 до ${BATCH_MAX_FILES_PER_UPLOAD} фотографий бланков`,
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
    return props.mode === 'append' ? 'Выберите листы' : 'Запустить расчёт'
  }
  const countLabel = formatSheetCountRu(stagedItems.value.length)
  return props.mode === 'append' ? `Догрузить (${countLabel})` : `Запустить расчёт (${countLabel})`
})

const canAddMore = computed(
  () => stagedItems.value.length < effectiveMaxFiles.value && !props.isSubmitting,
)

function revokeItemPreview(item: StagedSheetItem): void {
  if (item.previewUrl) {
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

watch(open, (isOpen) => {
  if (!isOpen) {
    clearStagedItems()
  } else {
    validationError.value = null
  }
})

onBeforeUnmount(() => {
  clearStagedItems()
})

function buildStagedItem(file: File): StagedSheetItem {
  const heic = isHeicFile(file)
  const previewUrl =
    !heic && typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function'
      ? URL.createObjectURL(file)
      : null

  return {
    id: createStagedItemId(),
    file,
    previewUrl,
    isHeic: heic,
    imageFailed: false,
  }
}

async function addIncomingFiles(incoming: readonly File[]): Promise<void> {
  if (props.isSubmitting || incoming.length === 0) return

  const seq = ++addSequence
  const currentFiles = stagedItems.value.map((item) => item.file)
  const result = await validateBatchFileAddition(currentFiles, incoming, effectiveMaxFiles.value)
  if (seq !== addSequence || !open.value || props.isSubmitting) return

  if (!result.ok) {
    validationError.value = result.error
    return
  }

  validationError.value = null
  const nextItems = result.files.map(buildStagedItem)
  stagedItems.value = [...stagedItems.value, ...nextItems]
}

function handleFileInputChange(event: Event): void {
  const input = event.target as HTMLInputElement | null
  const files = input?.files ? Array.from(input.files) : []
  if (input) {
    input.value = ''
  }
  if (files.length === 0) return
  void addIncomingFiles(files)
}

function openGalleryPicker(): void {
  if (!canAddMore.value) return
  galleryInputRef.value?.click()
}

function openCameraPicker(): void {
  if (!canAddMore.value) return
  cameraInputRef.value?.click()
}

function handleDragEnter(event: DragEvent): void {
  if (props.isSubmitting) return
  if (!event.dataTransfer?.types?.includes('Files')) return
  dragEnterDepth += 1
  isDragOver.value = true
}

function handleDragOver(event: DragEvent): void {
  if (props.isSubmitting) return
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
  if (props.isSubmitting) return
  const droppedFiles = event.dataTransfer?.files ? Array.from(event.dataTransfer.files) : []
  if (droppedFiles.length === 0) return
  void addIncomingFiles(droppedFiles)
}

function removeStagedItem(id: string): void {
  if (props.isSubmitting) return
  const target = stagedItems.value.find((item) => item.id === id)
  if (target) {
    revokeItemPreview(target)
  }
  stagedItems.value = stagedItems.value.filter((item) => item.id !== id)
  validationError.value = null
}

async function handleAddDemoSheets(): Promise<void> {
  if (!isMockMode || !canAddMore.value || isGeneratingDemo.value) return
  isGeneratingDemo.value = true
  try {
    const remaining = effectiveMaxFiles.value - stagedItems.value.length
    const { createDemoAuctionSheetFiles } = await import('@/utils/batchDemo')
    const demoFiles = await createDemoAuctionSheetFiles(remaining)
    if (demoFiles.length > 0) {
      await addIncomingFiles(demoFiles)
    }
  } finally {
    isGeneratingDemo.value = false
  }
}

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
      <input
        ref="galleryInputRef"
        type="file"
        multiple
        :accept="BATCH_ACCEPT_ATTR"
        class="sr-only"
        aria-label="Выбрать файлы аукционных листов"
        @change="handleFileInputChange"
      />
      <input
        ref="cameraInputRef"
        type="file"
        accept="image/*"
        capture="environment"
        class="sr-only"
        aria-label="Снять аукционный лист на камеру"
        @change="handleFileInputChange"
      />

      <!-- Interactive Dropzone (Desktop drag-drop + Mobile unified stage) -->
      <div
        class="rounded-lg border border-dashed px-4 py-4 transition-colors duration-150"
        :class="[
          isDragOver
            ? 'border-accent bg-accent-subtle/60'
            : activeError
              ? 'border-danger/45 bg-danger-bg/40'
              : 'border-border-strong bg-surface-inset/50',
        ]"
        @dragenter.prevent="handleDragEnter"
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
      >
        <div class="flex flex-col items-center text-center">
          <div class="w-full">
            <CapyMascot
              :state="activeError ? 'error' : undefined"
              :has-selected-files="stagedItems.length > 0"
              :is-drag-over="isDragOver"
              size="hero"
              :badge-text="mascotBadgeText"
            />
          </div>

          <!-- Desktop picker actions (>= 768px) -->
          <div class="mt-3 hidden flex-col items-center gap-2 md:flex">
            <p class="text-text-secondary text-[13px] leading-snug">
              Перетащите фотографии или сканы сюда либо выберите с компьютера
            </p>
            <div class="flex flex-wrap items-center justify-center gap-2">
              <BaseButton
                variant="secondary"
                size="sm"
                :disabled="!canAddMore"
                @click="openGalleryPicker"
              >
                <template #icon-left>
                  <Upload :size="15" :stroke-width="2" />
                </template>
                {{ stagedItems.length > 0 ? 'Добавить ещё фото' : 'Выбрать файлы' }}
              </BaseButton>

              <BaseButton
                v-if="isMockMode && stagedItems.length === 0 && canAddMore"
                variant="ghost"
                size="sm"
                :loading="isGeneratingDemo"
                @click="handleAddDemoSheets"
              >
                <template #icon-left>
                  <Sparkles :size="14" :stroke-width="2" />
                </template>
                Демо-листы
              </BaseButton>
            </div>
          </div>

          <!-- Mobile picker actions (< 768px): Camera + Gallery as in wireframe -->
          <div class="mt-3.5 grid w-full grid-cols-2 gap-2.5 md:hidden">
            <BaseButton
              variant="secondary"
              size="md"
              :disabled="!canAddMore"
              @click="openCameraPicker"
            >
              <template #icon-left>
                <Camera :size="17" :stroke-width="1.9" />
              </template>
              Камера
            </BaseButton>

            <BaseButton
              variant="secondary"
              size="md"
              :disabled="!canAddMore"
              @click="openGalleryPicker"
            >
              <template #icon-left>
                <ImagePlus :size="17" :stroke-width="1.9" />
              </template>
              Галерея
            </BaseButton>

            <div
              v-if="isMockMode && stagedItems.length === 0 && canAddMore"
              class="col-span-2 flex justify-center pt-0.5"
            >
              <BaseButton
                variant="ghost"
                size="sm"
                :loading="isGeneratingDemo"
                @click="handleAddDemoSheets"
              >
                <template #icon-left>
                  <Sparkles :size="14" :stroke-width="2" />
                </template>
                Загрузить демо-листы
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Strict validation or upload error alert -->
      <div
        v-if="activeError"
        role="alert"
        class="bg-danger-bg text-danger flex items-start gap-2.5 rounded-md px-3.5 py-2.5 text-[13px] leading-snug"
      >
        <AlertCircle :size="16" :stroke-width="2" class="mt-0.5 shrink-0" />
        <p class="min-w-0 flex-1">{{ activeError }}</p>
      </div>

      <!-- Staged files thumbnails -->
      <section
        v-if="stagedItems.length > 0"
        aria-label="Выбранные аукционные листы"
        class="flex flex-col gap-2"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="text-text-secondary text-[13px] font-medium tabular-nums">
            Выбрано {{ stagedItems.length }} из {{ effectiveMaxFiles }}
          </span>
          <button
            type="button"
            class="text-text-secondary hover:text-text-primary cursor-pointer text-[13px] font-medium transition-colors disabled:opacity-50"
            :disabled="isSubmitting"
            @click="clearStagedItems"
          >
            Очистить всё
          </button>
        </div>

        <ul class="grid grid-cols-3 gap-2.5 sm:grid-cols-4">
          <li
            v-for="(item, index) in stagedItems"
            :key="item.id"
            class="border-border bg-surface relative flex flex-col overflow-hidden rounded-md border"
          >
            <div class="bg-surface-inset relative aspect-[3/4] w-full overflow-hidden">
              <img
                v-if="item.previewUrl && !item.imageFailed"
                :src="item.previewUrl"
                :alt="item.file.name"
                class="h-full w-full object-cover"
                @error="item.imageFailed = true"
              />
              <div
                v-else
                class="text-text-secondary flex h-full w-full flex-col items-center justify-center gap-1 px-2 text-center"
              >
                <FileImage :size="22" :stroke-width="1.7" />
                <span class="text-[11px] font-medium uppercase">
                  {{ item.isHeic ? 'HEIC' : 'Фото' }}
                </span>
              </div>

              <span
                class="bg-success text-text-on-accent absolute bottom-1.5 left-1.5 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
              >
                <Check :size="10" :stroke-width="2.5" />
                {{ index + 1 }}
              </span>

              <button
                type="button"
                class="bg-text-primary/75 text-surface hover:bg-text-primary absolute top-1.5 right-1.5 flex h-6 w-6 cursor-pointer items-center justify-center rounded-full transition-colors disabled:opacity-50"
                :aria-label="`Удалить файл ${item.file.name}`"
                :disabled="isSubmitting"
                @click="removeStagedItem(item.id)"
              >
                <X :size="13" :stroke-width="2.2" />
              </button>
            </div>

            <div class="flex flex-col gap-0.5 px-2 py-1.5">
              <span class="text-text-primary truncate text-[11px] font-medium">
                {{ item.file.name }}
              </span>
              <span class="text-text-muted text-[10px] tabular-nums">
                {{ formatFileSizeRu(item.file.size) }}
              </span>
            </div>
          </li>
        </ul>
      </section>
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
