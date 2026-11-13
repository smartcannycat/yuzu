<script setup lang="ts">
import { BrandLogo } from '@/components/ui'

interface Props {
  initials: string
  displayName: string
  subtitle?: string
}

withDefaults(defineProps<Props>(), {
  subtitle: 'Интеллект японских автоаукционов',
})

const emit = defineEmits<{
  openProfile: []
}>()
</script>

<template>
  <header class="flex items-center justify-between gap-3">
    <BrandLogo layout="header" :subtitle="subtitle" responsive-subtitle />

    <div class="flex shrink-0 items-center gap-2.5">
      <slot name="actions" />

      <button
        type="button"
        aria-label="Открыть меню профиля"
        class="border-border bg-surface hover:bg-surface-hover active:bg-surface-inset focus-visible:outline-accent flex h-10 max-w-[200px] cursor-pointer items-center gap-2 rounded-full border pr-3 pl-1.5 transition-colors duration-[var(--duration-quick)] focus-visible:outline-2 focus-visible:outline-offset-2"
        @click="emit('openProfile')"
      >
        <span
          class="bg-accent-subtle text-accent flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold"
        >
          {{ initials }}
        </span>
        <span class="text-text-primary truncate text-[13px] font-medium">
          {{ displayName }}
        </span>
      </button>
    </div>
  </header>
</template>
