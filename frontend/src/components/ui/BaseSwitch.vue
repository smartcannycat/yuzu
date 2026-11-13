<script setup lang="ts">
import { computed, ref, useId } from 'vue'

interface Props {
  id?: string
  label?: string
  description?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const modelValue = defineModel<boolean>({ default: false })
const isInitialized = ref(false)

const fallbackId = useId()
const switchId = computed(() => props.id ?? `yuzu-switch-${fallbackId}`)
const labelId = computed(() => `${switchId.value}-label`)
const descId = computed(() => `${switchId.value}-desc`)

function toggle() {
  if (props.disabled) return
  isInitialized.value = true
  modelValue.value = !modelValue.value
}
</script>

<template>
  <div
    class="inline-flex min-h-11 items-center gap-3.5 select-none"
    :class="disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'"
    @click="toggle"
  >
    <button
      :id="switchId"
      type="button"
      role="switch"
      :aria-checked="modelValue"
      :aria-labelledby="label ? labelId : undefined"
      :aria-describedby="description ? descId : undefined"
      :disabled="disabled"
      :data-on="modelValue ? 'true' : 'false'"
      class="yuzu-toggle focus-visible:outline-accent relative inline-flex h-[26px] w-[52px] shrink-0 items-center rounded-full p-0.5 before:absolute before:-inset-x-1 before:-inset-y-2.5 before:content-[''] focus-visible:outline-2 focus-visible:outline-offset-2"
      :class="[
        isInitialized ? 'is-init' : '',
        modelValue ? 'bg-accent' : 'bg-border',
        disabled ? 'cursor-not-allowed' : 'cursor-pointer',
      ]"
      @click.stop="toggle"
    >
      <span
        aria-hidden="true"
        class="yuzu-toggle-thumb bg-surface shadow-thumb pointer-events-none block h-[22px] w-[28px] rounded-full"
      />
    </button>

    <div v-if="label || description" class="flex flex-col">
      <span
        v-if="label"
        :id="labelId"
        class="text-text-primary text-[14px] leading-snug font-medium"
      >
        {{ label }}
      </span>
      <span v-if="description" :id="descId" class="text-text-secondary text-[12px] leading-snug">
        {{ description }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.yuzu-toggle {
  transition: background-color var(--toggle-track) var(--ease-smooth-out);
}

.yuzu-toggle-thumb {
  transform: translateX(0);
  will-change: transform;
}

.yuzu-toggle[data-on='true'] .yuzu-toggle-thumb {
  transform: translateX(var(--toggle-travel));
}

.yuzu-toggle.is-init[data-on='true'] .yuzu-toggle-thumb {
  animation: yuzu-toggle-on var(--toggle-dur) var(--toggle-ease) both;
}

.yuzu-toggle.is-init[data-on='false'] .yuzu-toggle-thumb {
  animation: yuzu-toggle-off var(--toggle-dur) var(--toggle-ease) both;
}

@keyframes yuzu-toggle-on {
  0% {
    transform: translateX(0);
  }
  55% {
    transform: translateX(calc(var(--toggle-travel) + var(--toggle-ov1)));
  }
  80% {
    transform: translateX(calc(var(--toggle-travel) - var(--toggle-ov2)));
  }
  100% {
    transform: translateX(var(--toggle-travel));
  }
}

@keyframes yuzu-toggle-off {
  0% {
    transform: translateX(var(--toggle-travel));
  }
  55% {
    transform: translateX(calc(0px - var(--toggle-ov1)));
  }
  80% {
    transform: translateX(var(--toggle-ov2));
  }
  100% {
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .yuzu-toggle-thumb {
    animation: none !important;
  }
}
</style>
