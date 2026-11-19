<script setup lang="ts">
import { Check, FileImage, X } from '@lucide/vue'

import type { StagedSheetItem } from '@/components/lots/composables/useBatchUploadStaging'
import { formatFileSizeRu } from '@/utils/batchFiles'

interface Props {
  items: readonly StagedSheetItem[]
  maxFiles: number
  isSubmitting: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  clearAll: []
  removeItem: [id: string]
  imageError: [id: string]
}>()
</script>

<template>
  <section
    v-if="items.length > 0"
    aria-label="Выбранные аукционные листы"
    class="flex flex-col gap-2"
  >
    <div class="flex items-center justify-between gap-2">
      <span class="text-text-secondary text-[13px] font-medium tabular-nums">
        Выбрано {{ items.length }} из {{ maxFiles }}
      </span>
      <button
        type="button"
        class="text-text-secondary hover:text-text-primary cursor-pointer text-[13px] font-medium transition-colors disabled:opacity-50"
        :disabled="isSubmitting"
        @click="emit('clearAll')"
      >
        Очистить всё
      </button>
    </div>

    <ul class="grid grid-cols-3 gap-2.5 sm:grid-cols-4">
      <li
        v-for="(item, index) in items"
        :key="item.id"
        class="border-border bg-surface relative flex flex-col overflow-hidden rounded-md border"
      >
        <div class="bg-surface-inset relative aspect-[3/4] w-full overflow-hidden">
          <img
            v-if="item.previewUrl && !item.imageFailed"
            :src="item.previewUrl"
            :alt="item.file.name"
            class="h-full w-full object-cover"
            @error="emit('imageError', item.id)"
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
            @click="emit('removeItem', item.id)"
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
</template>
