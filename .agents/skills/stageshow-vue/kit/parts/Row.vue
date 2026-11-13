<script setup lang="ts">
import { computed, isVNode, type CSSProperties } from 'vue'
import Bar from '../Bar.vue'
import './Row.css'

export interface RowProps {
  lead?: any
  title?: any
  subtitle?: any
  meta?: any
  preview?: number[] | any
  unread?: boolean
  selected?: boolean
  pad?: number
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<RowProps>(), {
  pad: 12,
})

function isRenderableObject(v: any): boolean {
  return isVNode(v) || typeof v === 'function' || (typeof v === 'object' && v !== null)
}

function asComponent(v: any) {
  if (typeof v === 'function') return v
  if (isVNode(v) || Array.isArray(v)) return () => v
  return v
}

const isPreviewNumbers = computed(
  () =>
    Array.isArray(props.preview) &&
    props.preview.every((w) => typeof w === 'number'),
)
</script>

<template>
  <div
    :class="['ss-row', props.className, props.class]"
    :data-selected="props.selected || undefined"
    :data-unread="props.unread || undefined"
    :data-lead="props.lead || $slots.lead ? '' : undefined"
    :style="{ ['--ss-row-pad' as any]: `${props.pad}px`, ...props.style }"
    v-bind="$attrs"
  >
    <span v-if="props.unread" class="ss-row__dot" aria-hidden="true" />

    <span v-if="props.lead || $slots.lead" class="ss-row__lead">
      <slot name="lead">
        <component :is="asComponent(props.lead)" v-if="isRenderableObject(props.lead)" />
        <template v-else>{{ props.lead }}</template>
      </slot>
    </span>

    <span class="ss-row__body">
      <span class="ss-row__head">
        <span class="ss-row__title">
          <slot name="title">
            <component :is="asComponent(props.title)" v-if="isRenderableObject(props.title)" />
            <template v-else>{{ props.title }}</template>
          </slot>
        </span>
        <span v-if="props.meta !== undefined || $slots.meta" class="ss-row__meta">
          <slot name="meta">
            <component :is="asComponent(props.meta)" v-if="isRenderableObject(props.meta)" />
            <template v-else>{{ props.meta }}</template>
          </slot>
        </span>
      </span>

      <span v-if="props.subtitle !== undefined || $slots.subtitle" class="ss-row__subtitle">
        <slot name="subtitle">
          <component :is="asComponent(props.subtitle)" v-if="isRenderableObject(props.subtitle)" />
          <template v-else>{{ props.subtitle }}</template>
        </slot>
      </span>
    </span>

    <template v-if="props.preview !== undefined || $slots.preview">
      <span v-if="isPreviewNumbers" class="ss-row__preview" aria-hidden="true">
        <Bar v-for="(w, i) in (props.preview as number[])" :key="i" :w="w" :h="6" :tone="2" />
      </span>
      <span v-else class="ss-row__preview" data-text>
        <slot name="preview">
          <component :is="asComponent(props.preview)" v-if="isRenderableObject(props.preview)" />
          <template v-else>{{ props.preview }}</template>
        </slot>
      </span>
    </template>

    <slot />
  </div>
</template>
