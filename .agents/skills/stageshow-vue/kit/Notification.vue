<script setup lang="ts">
import { isVNode } from 'vue'
import './phone.css'

export interface NotificationProps {
  icon?: any
  title?: any
  body?: any
  time?: string
  banner?: boolean
  className?: string
  class?: any
}

const props = withDefaults(defineProps<NotificationProps>(), {
  time: 'now',
})

function isRenderableObject(v: any): boolean {
  return isVNode(v) || typeof v === 'function' || (typeof v === 'object' && v !== null)
}

function asComponent(v: any) {
  if (typeof v === 'function') return v
  if (isVNode(v) || Array.isArray(v)) return () => v
  return v
}
</script>

<template>
  <div :class="['ss-notification', props.className, props.class]" :data-banner="props.banner || undefined">
    <span class="ss-notification__icon">
      <slot name="icon">
        <component :is="asComponent(props.icon)" v-if="isRenderableObject(props.icon)" />
        <template v-else>{{ props.icon }}</template>
      </slot>
    </span>
    <span class="ss-notification__text">
      <span class="ss-notification__head">
        <span class="ss-notification__title">
          <slot name="title">
            <component :is="asComponent(props.title)" v-if="isRenderableObject(props.title)" />
            <template v-else>{{ props.title }}</template>
          </slot>
        </span>
        <span class="ss-notification__time">{{ props.time }}</span>
      </span>
      <span v-if="props.body !== undefined || $slots.body" class="ss-notification__body">
        <slot name="body">
          <component :is="asComponent(props.body)" v-if="isRenderableObject(props.body)" />
          <template v-else>{{ props.body }}</template>
        </slot>
      </span>
    </span>
  </div>
</template>
