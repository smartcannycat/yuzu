<script setup lang="ts">
interface Props {
  title?: string
}

defineProps<Props>()
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-if="title" class="text-text-secondary px-1 text-[13px] font-medium">
      {{ title }}
    </div>
    <div class="border-border bg-surface shadow-card overflow-hidden rounded-md border">
      <slot />
    </div>
  </div>
</template>
