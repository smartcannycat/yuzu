<script setup lang="ts">
import { h, ref, computed, type VNode } from 'vue'
import {
  type CursorKind,
  type CursorStyle,
  GLYPHS,
  HOTSPOT,
  ARROW_HOTSPOT,
} from './cursor'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  cursorStyle?: CursorStyle
  style?: CursorStyle
  kind: CursorKind
}>()

const activeStyle = computed<CursorStyle>(() => props.cursorStyle ?? props.style ?? 'real')

const rootEl = ref<HTMLDivElement | null>(null)

const cursorKinds = Object.keys(GLYPHS) as CursorKind[]

function SolidArrow(): VNode {
  return h(
    'svg',
    {
      width: '22',
      height: '22',
      viewBox: '0 0 22 22',
      class: 'ss-cursor__arrow',
      'aria-hidden': 'true',
    },
    [h('path', { d: 'M4 3 18.5 9.6 11.8 11.8 9.6 18.5Z' })],
  )
}

function getGlyph(k: CursorKind) {
  if (activeStyle.value === 'arrow' && k === 'pointer') return SolidArrow
  return GLYPHS[k]
}

function getHot(k: CursorKind) {
  if (activeStyle.value === 'arrow' && k === 'pointer') return ARROW_HOTSPOT
  return HOTSPOT[k]
}

function getShown() {
  if (activeStyle.value === 'arrow') {
    return props.kind !== 'ibeam' ? 'pointer' : props.kind
  }
  return props.kind
}

function getGlyphStyle(k: CursorKind) {
  const hot = getHot(k)
  return {
    marginLeft: `${-hot.x}px`,
    marginTop: `${-hot.y}px`,
    transformOrigin: `${hot.x}px ${hot.y}px`,
  }
}

defineExpose({
  el: rootEl,
  rootEl,
})
</script>

<template>
  <div
    ref="rootEl"
    class="ss-cursor"
    :data-style="activeStyle"
    :data-kind="props.kind"
    aria-hidden="true"
  >
    <span v-if="activeStyle === 'touch'" class="ss-cursor__streak" />
    <div class="ss-cursor__press">
      <span v-if="activeStyle === 'circle' || activeStyle === 'touch'" class="ss-cursor__dot" />
      <template v-else>
        <template v-for="k in cursorKinds" :key="k">
          <div
            v-if="!(activeStyle === 'arrow' && k !== 'pointer' && k !== 'ibeam')"
            class="ss-cursor__glyph"
            :data-glyph="k"
            :data-active="k === getShown() || undefined"
            :style="getGlyphStyle(k)"
          >
            <component :is="getGlyph(k)" />
          </div>
        </template>
      </template>
    </div>
  </div>
</template>
