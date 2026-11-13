<script setup lang="ts">
import './window.css'

defineProps<{
  still?: boolean
}>()
</script>

<template>
  <span class="ss-term__caret" :data-still="still || undefined" aria-hidden="true" />
</template>
