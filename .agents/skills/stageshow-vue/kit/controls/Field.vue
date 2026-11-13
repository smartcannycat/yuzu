<script setup lang="ts">
import { ref, computed, onMounted, watch, type CSSProperties } from 'vue'
import Icon from '../parts/Icon.vue'
import './Field.css'

export interface FieldProps {
  label?: any
  value: string
  placeholder?: string
  focused?: boolean
  password?: boolean
  status?: 'valid' | 'error'
  chip?: boolean
  remove?: string
  leading?: any
  trailing?: any
  box?: Record<string, any>
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = defineProps<FieldProps>()

const held = ref('')
const text = ref<HTMLSpanElement | null>(null)

watch(
  () => [props.chip, props.value],
  () => {
    if (props.chip || props.value) {
      held.value = props.chip ? props.value : ''
    }
  },
  { immediate: true },
)

const out = computed(() => !props.chip && !props.value && !!held.value)

function letGo() {
  if (!held.value) return
  held.value = ''
}

onMounted(() => {
  const el = text.value
  if (!el) return
  const check = () => {
    if (Number(getComputedStyle(el).opacity) === 0) letGo()
  }
  const settle = (event: TransitionEvent) => {
    if (event.target === el && event.propertyName === 'opacity') check()
  }
  el.addEventListener('transitionend', settle)
  el.addEventListener('transitioncancel', settle)
})

const shown = computed(() => (out.value ? held.value : props.value))
</script>

<template>
  <div
    :class="['ss-field', props.className, props.class]"
    :data-focused="props.focused || undefined"
    :data-status="props.status"
    :data-filled="props.value ? true : undefined"
    :style="props.style"
  >
    <span v-if="props.label || $slots.label" class="ss-field__label">
      <slot name="label">{{ props.label }}</slot>
    </span>

    <div
      data-cursor="ibeam"
      :class="['ss-field__box', props.box?.className, props.box?.class]"
      v-bind="props.box"
    >
      <slot name="leading">
        <component :is="() => props.leading" v-if="props.leading" />
      </slot>

      <span class="ss-field__text">
        <span v-if="props.placeholder" class="ss-field__placeholder">
          {{ props.placeholder }}
        </span>

        <span
          ref="text"
          class="ss-field__value"
          :data-password="props.password || undefined"
          :data-chip="props.chip || out || undefined"
          :data-leaving="out || undefined"
          :data-removable="props.remove !== undefined || undefined"
        >
          <span class="ss-field__chars">
            {{ props.password ? '•'.repeat(shown.length) : shown }}
          </span>

          <span
            v-if="props.remove !== undefined"
            class="ss-field__x"
            role="button"
            data-cursor="hand"
            :data-target="props.remove || undefined"
          >
            <Icon name="close" :size="10" :stroke="1.8" />
          </span>
        </span>

        <!-- Caret restarts on keystroke -->
        <span v-if="props.focused" :key="props.value.length" class="ss-field__caret" />
      </span>

      <svg
        v-if="props.status === 'valid'"
        class="ss-field__ok"
        viewBox="0 0 16 16"
        width="14"
        height="14"
        aria-hidden="true"
      >
        <path d="M3.5 8.5 6.5 11.5 12.5 4.5" pathLength="1" />
      </svg>

      <slot name="trailing">
        <component :is="() => props.trailing" v-if="props.trailing" />
      </slot>
    </div>
  </div>
</template>
