<script setup lang="ts">
export interface TtxItem {
  label: string
  value: string
  span?: 1 | 2
}

interface Props {
  items: TtxItem[]
  columns?: 2 | 3
}

withDefaults(defineProps<Props>(), {
  columns: 2,
})
</script>

<template>
  <dl
    class="bg-surface-inset grid gap-x-5 gap-y-3.5 rounded-sm p-4"
    :class="
      columns === 3
        ? 'grid-cols-1 min-[360px]:grid-cols-2 md:grid-cols-3 print:grid-cols-3'
        : 'grid-cols-1 min-[360px]:grid-cols-2'
    "
  >
    <div
      v-for="item in items"
      :key="item.label"
      class="flex min-w-0 flex-col gap-0.5"
      :class="item.span === 2 ? 'min-[360px]:col-span-2' : ''"
    >
      <dt class="text-text-secondary text-[12px] leading-snug font-normal">
        {{ item.label }}
      </dt>
      <dd class="text-text-primary text-[15px] leading-snug font-medium tabular-nums">
        {{ item.value }}
      </dd>
    </div>
  </dl>
</template>
