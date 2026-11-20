<script setup lang="ts">
import { Camera, ImagePlus, Sparkles, Upload } from '@lucide/vue'
import { computed, ref } from 'vue'

import { isMockMode } from '@/api'
import { CapyMascot } from '@/components/mascot'
import { BaseButton } from '@/components/ui'
import { BATCH_ACCEPT_ATTR } from '@/utils/batchFiles'

interface Props {
  hasSelectedFiles: boolean
  hasError: boolean
  isDragOver: boolean
  canAddMore: boolean
  isGeneratingDemo: boolean
  mascotBadgeText: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  filesSelected: [files: File[]]
  addDemo: []
  dragEnter: [event: DragEvent]
  dragOver: [event: DragEvent]
  dragLeave: []
  dropFiles: [event: DragEvent]
}>()

const galleryInputRef = ref<HTMLInputElement | null>(null)
const cameraInputRef = ref<HTMLInputElement | null>(null)

const showDemoButton = computed(() => isMockMode && !props.hasSelectedFiles && props.canAddMore)

function handleInputChange(event: Event): void {
  const input = event.target as HTMLInputElement | null
  const files = input?.files ? Array.from(input.files) : []
  if (input) {
    input.value = ''
  }
  if (files.length > 0) {
    emit('filesSelected', files)
  }
}

function openGalleryPicker(): void {
  if (!props.canAddMore) return
  galleryInputRef.value?.click()
}

function openCameraPicker(): void {
  if (!props.canAddMore) return
  cameraInputRef.value?.click()
}
</script>

<template>
  <div>
    <input
      ref="galleryInputRef"
      type="file"
      multiple
      :accept="BATCH_ACCEPT_ATTR"
      class="sr-only"
      aria-label="Выбрать файлы аукционных листов"
      @change="handleInputChange"
    />
    <input
      ref="cameraInputRef"
      type="file"
      accept="image/*"
      capture="environment"
      class="sr-only"
      aria-label="Снять аукционный лист на камеру"
      @change="handleInputChange"
    />

    <div
      class="rounded-lg border border-dashed px-4 py-4 transition-colors duration-150"
      :class="[
        isDragOver
          ? 'border-accent bg-accent-subtle/60'
          : hasError
            ? 'border-danger/45 bg-danger-bg/40'
            : 'border-border-strong bg-surface-inset/50',
      ]"
      @dragenter.prevent="emit('dragEnter', $event)"
      @dragover.prevent="emit('dragOver', $event)"
      @dragleave.prevent="emit('dragLeave')"
      @drop.prevent="emit('dropFiles', $event)"
    >
      <div class="flex flex-col items-center text-center">
        <div class="w-full">
          <CapyMascot
            :state="hasError ? 'error' : undefined"
            :has-selected-files="hasSelectedFiles"
            :is-drag-over="isDragOver"
            size="hero"
            :badge-text="mascotBadgeText"
          />
        </div>

        <p class="text-text-secondary mt-3 hidden text-[13px] leading-snug md:block">
          Перетащите фотографии или сканы сюда либо выберите с компьютера
        </p>

        <div
          class="mt-3.5 grid w-full grid-cols-2 gap-2.5 md:mt-2 md:flex md:w-auto md:flex-wrap md:justify-center md:gap-2"
        >
          <BaseButton
            variant="secondary"
            size="md"
            class="md:hidden"
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
            class="md:hidden"
            :disabled="!canAddMore"
            @click="openGalleryPicker"
          >
            <template #icon-left>
              <ImagePlus :size="17" :stroke-width="1.9" />
            </template>
            Галерея
          </BaseButton>

          <BaseButton
            variant="secondary"
            size="sm"
            class="hidden md:inline-flex"
            :disabled="!canAddMore"
            @click="openGalleryPicker"
          >
            <template #icon-left>
              <Upload :size="15" :stroke-width="2" />
            </template>
            {{ hasSelectedFiles ? 'Добавить ещё фото' : 'Выбрать файлы' }}
          </BaseButton>

          <BaseButton
            v-if="showDemoButton"
            variant="ghost"
            size="sm"
            class="col-span-2 justify-self-center md:col-span-1"
            :loading="isGeneratingDemo"
            @click="emit('addDemo')"
          >
            <template #icon-left>
              <Sparkles :size="14" :stroke-width="2" />
            </template>
            Демо-листы
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>
