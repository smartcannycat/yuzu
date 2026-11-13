<script setup lang="ts">
import { ref, computed, watch, type CSSProperties } from 'vue'
import './ios.css'

export interface KeyboardProps {
  typed?: string
  shift?: boolean
  suggestions?: [string, string, string]
  pressed?: string | null
  dark?: boolean
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<KeyboardProps>(), {
  typed: '',
  suggestions: () => ['I', 'The', 'I’m'],
})

const ROWS = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm']

const pop = ref<{ ch: string; n: number } | null>(null)
let lastTyped = props.typed
let popTimer = 0

watch(
  () => props.typed,
  (next) => {
    const was = lastTyped
    lastTyped = next
    if (next.length <= was.length || !next.startsWith(was)) return
    const ch = next[next.length - 1].toLowerCase()
    pop.value = { ch, n: (pop.value?.n ?? 0) + 1 }
    clearTimeout(popTimer)
    popTimer = window.setTimeout(() => {
      pop.value = null
    }, 140)
  },
)

const auto = computed(() => props.typed === '' || /[.!?]\s$/.test(props.typed))
const upper = computed(() => props.shift ?? auto.value)

function isDown(k: string) {
  return props.pressed === k || (k.length === 1 && pop.value?.ch === k)
}
</script>

<template>
  <div :class="['ss-kb', props.className, props.class]" :data-dark="props.dark || undefined" :style="props.style">
    <div class="ss-kb__suggest">
      <span v-for="(w, i) in props.suggestions" :key="i">{{ w }}</span>
    </div>

    <div v-for="(row, r) in ROWS" :key="r" class="ss-kb__row" :data-row="r">
      <span v-if="r === 2" class="ss-kb__key ss-kb__key--wide" :data-down="isDown('shift') || undefined">
        <!-- shift / shift-on glyph -->
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path
            d="M12 3.6 3.4 12.4H8v7.4h8v-7.4h4.6Z"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linejoin="round"
            stroke-linecap="round"
            :style="{ fill: upper ? 'currentColor' : 'none' }"
          />
        </svg>
      </span>

      <span v-for="k in row.split('')" :key="k" class="ss-kb__key" :data-down="isDown(k) || undefined">
        {{ upper ? k.toUpperCase() : k }}
        <span v-if="pop?.ch === k" :key="pop.n" class="ss-kb__callout" aria-hidden="true">
          {{ upper ? k.toUpperCase() : k }}
        </span>
      </span>

      <span v-if="r === 2" class="ss-kb__key ss-kb__key--wide" :data-down="isDown('delete') || undefined">
        <!-- delete glyph -->
        <svg viewBox="0 0 26 24" width="24" height="22" aria-hidden="true">
          <path
            d="M8.6 4.5h13.2a2.2 2.2 0 0 1 2.2 2.2v10.6a2.2 2.2 0 0 1-2.2 2.2H8.6L2 12Z"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <path
            d="m11.4 8.6 6.8 6.8m0-6.8-6.8 6.8"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        </svg>
      </span>
    </div>

    <div class="ss-kb__row ss-kb__row--bottom">
      <span class="ss-kb__key ss-kb__key--mode" :data-down="isDown('123') || undefined">
        123
      </span>
      <span class="ss-kb__key ss-kb__key--space" :data-down="isDown('space') || isDown(' ') || undefined" />
      <span class="ss-kb__key ss-kb__key--mode" :data-down="isDown('return') || undefined">
        <!-- return glyph -->
        <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
          <path
            d="M19.5 5.5v6.2a2.3 2.3 0 0 1-2.3 2.3H5"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <path
            d="m9.2 9.6-4.4 4.4 4.4 4.4"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        </svg>
      </span>
    </div>

    <div class="ss-kb__below">
      <!-- emoji glyph -->
      <svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true">
        <circle cx="14" cy="14" r="12.5" fill="currentColor" />
        <ellipse cx="10" cy="10.6" rx="1.5" ry="2.1" fill="var(--ss-kb-sheet)" />
        <ellipse cx="18" cy="10.6" rx="1.5" ry="2.1" fill="var(--ss-kb-sheet)" />
        <path d="M7.4 15.2c.9 3.6 3.6 5.8 6.6 5.8s5.7-2.2 6.6-5.8Z" fill="var(--ss-kb-sheet)" />
      </svg>
      <!-- mic glyph -->
      <svg viewBox="0 0 24 28" width="22" height="26" aria-hidden="true">
        <rect x="7.6" y="2" width="8.8" height="15" rx="4.4" fill="currentColor" />
        <path
          d="M4.2 12.8a7.8 7.8 0 0 0 15.6 0M12 20.6V26M8 26h8"
          fill="none"
          stroke="currentColor"
          stroke-width="1.9"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
      </svg>
    </div>
  </div>
</template>
