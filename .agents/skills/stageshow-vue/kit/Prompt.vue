<script setup lang="ts">
import './window.css'

export interface PromptProps {
  path?: string
  className?: string
  class?: any
}

const props = withDefaults(defineProps<PromptProps>(), {
  path: '~',
})
</script>

<template>
  <div :class="['ss-term__line', 'ss-term__prompt', props.className, props.class]">
    <span class="ss-term__path">{{ props.path }}</span>
    <span class="ss-term__sigil">❯</span>
    <span class="ss-term__cmd">
      <slot />
    </span>
  </div>
</template>
