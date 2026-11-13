<script setup lang="ts">
import { computed } from 'vue'
import './phone.css'

export interface LockScreenProps {
  date?: string
  time?: string
  controls?: boolean
  stack?: 'bottom' | 'top'
  size?: 'full' | 'satellite'
  clock?: boolean
  className?: string
  class?: any
}

const props = withDefaults(defineProps<LockScreenProps>(), {
  date: 'Tuesday, October 21',
  time: '9:41',
  controls: true,
  stack: 'bottom',
  size: 'full',
  clock: true,
})
</script>

<template>
  <div
    :class="['ss-lock', props.className, props.class]"
    :data-size="props.size"
    :data-clock="props.clock ? undefined : 'off'"
  >
    <div v-if="props.clock" class="ss-lock__date">{{ props.date }}</div>
    <div v-if="props.clock" class="ss-lock__clock">{{ props.time }}</div>
    <div class="ss-lock__stack" :data-at="props.stack">
      <slot />
    </div>
    <div v-if="props.controls && props.size === 'full'" class="ss-lock__controls">
      <span class="ss-lock__control">
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path
            fill="currentColor"
            fill-rule="evenodd"
            d="M7.6 1.6h8.8a1.6 1.6 0 0 1 1.6 1.6v1.9H6V3.2a1.6 1.6 0 0 1 1.6-1.6ZM6 6h12l-2.6 4v10.4a2 2 0 0 1-2 2h-2.8a2 2 0 0 1-2-2V10ZM10.6 14a1.4 1.4 0 1 0 2.8 0 1.4 1.4 0 1 0-2.8 0Z"
          />
        </svg>
      </span>
      <span class="ss-lock__control">
        <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
          <path
            fill="currentColor"
            fill-rule="evenodd"
            d="M4.6 6.6h3.3l1.2-1.8a1.3 1.3 0 0 1 1.1-.6h3.6a1.3 1.3 0 0 1 1.1.6l1.2 1.8h3.3A2.6 2.6 0 0 1 22 9.2v8.6a2.6 2.6 0 0 1-2.6 2.6H4.6A2.6 2.6 0 0 1 2 17.8V9.2a2.6 2.6 0 0 1 2.6-2.6ZM7.5 13.4a4.5 4.5 0 1 0 9 0 4.5 4.5 0 1 0-9 0ZM9 13.4a3 3 0 1 0 6 0 3 3 0 1 0-6 0Z"
          />
        </svg>
      </span>
    </div>
  </div>
</template>
