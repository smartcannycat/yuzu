<script setup lang="ts">
import './keys.css'
import type { Keys, KeysAt } from './keys'

defineProps<{
  rows: (Keys | null)[]
  at: KeysAt
}>()
</script>

<template>
  <template v-for="row in rows" :key="row ? row.id : undefined">
    <div v-if="row" class="ss-keys" :data-show="row.show || undefined" :data-at="at" aria-hidden="true">
      <kbd v-for="(c, i) in row.caps" :key="i" class="ss-key" :data-down="row.down || undefined">
        {{ c }}
      </kbd>
    </div>
  </template>
</template>
