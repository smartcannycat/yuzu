<script setup lang="ts">
import { OctagonAlert, Trash2 } from '@lucide/vue'

import { BaseButton, BottomSheet } from '@/components/ui'

interface Props {
  make: string
  model: string
  isDeleting: boolean
  errorMessage: string | null
}

defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  confirm: []
}>()
</script>

<template>
  <BottomSheet
    v-model:open="open"
    title="Удалить лот?"
    max-width="sm"
    close-label="Отменить удаление"
    :persistent="isDeleting"
  >
    <div class="flex flex-col gap-4">
      <p class="text-text-secondary text-[14px] leading-relaxed">
        Лот «{{ make }} {{ model }}» будет убран из списка и фильтров.
      </p>

      <div
        v-if="errorMessage"
        role="alert"
        class="bg-danger-subtle border-danger/25 text-danger flex items-center gap-2 rounded-md border px-3 py-2 text-[13px] font-medium"
      >
        <OctagonAlert :size="15" class="shrink-0" />
        <span>{{ errorMessage }}</span>
      </div>

      <div class="flex items-center justify-end gap-2 pt-1">
        <BaseButton variant="secondary" size="md" pill :disabled="isDeleting" @click="open = false">
          Отмена
        </BaseButton>
        <BaseButton
          variant="destructive"
          size="md"
          pill
          :loading="isDeleting"
          @click="emit('confirm')"
        >
          <template #icon-left>
            <Trash2 :size="15" />
          </template>
          Удалить лот
        </BaseButton>
      </div>
    </div>
  </BottomSheet>
</template>
