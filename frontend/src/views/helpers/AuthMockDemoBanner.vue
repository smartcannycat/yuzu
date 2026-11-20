<script setup lang="ts">
import { Sparkles } from '@lucide/vue'

import { BaseBadge, BaseButton } from '@/components/ui'

interface Props {
  email: string
  disabled: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  apply: []
}>()
</script>

<template>
  <div
    class="border-border bg-surface flex items-center justify-between gap-3 rounded-md border px-4 py-3"
  >
    <div class="flex min-w-0 flex-col gap-0.5">
      <div class="flex items-center gap-1.5">
        <BaseBadge variant="neutral" size="sm">
          <template #icon>
            <Sparkles :size="12" :stroke-width="2" />
          </template>
          Mock API
        </BaseBadge>
        <span class="text-text-secondary truncate text-[12px]">
          {{ email }}
        </span>
      </div>
      <span class="text-text-muted text-[12px]"> Демо-доступ для проверки без бэкенда </span>
    </div>

    <BaseButton variant="secondary" size="sm" :disabled="disabled" @click="emit('apply')">
      Заполнить
    </BaseButton>
  </div>
</template>
