<script setup lang="ts">
import { computed, isVNode, useSlots, type CSSProperties } from 'vue'
import './window.css'

defineOptions({ inheritAttrs: false })

export interface WindowProps {
  url?: any
  urlShape?: 'rounded' | 'pill'
  tabs?: any[]
  nav?: boolean
  title?: string
  sidebar?: any
  sidebarWidth?: number
  sidebarStyle?: 'flush' | 'floating'
  toolbar?: any
  lead?: any
  body?: Record<string, any>
  receded?: boolean
  chrome?: 'native' | 'glass' | 'terminal' | 'card' | 'hairline'
  lights?: 'color' | 'grey' | 'white'
  lightsSize?: 'standard' | 'large'
  barSize?: 'standard' | 'tall'
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<WindowProps>(), {
  sidebarWidth: 180,
})

const slots = useSlots()

const hasSidebar = computed(() => props.sidebar !== undefined || !!slots.sidebar)
const hasUrl = computed(() => props.url !== undefined || !!slots.url)
const hasTitle = computed(() => props.title !== undefined || !!slots.title)
const hasTabs = computed(() => Boolean(props.tabs && props.tabs.length))
const hasToolbar = computed(() => props.toolbar !== undefined || !!slots.toolbar)
const hasLead = computed(() => props.lead !== undefined || !!slots.lead)

const large = computed(() => (props.lightsSize === 'large' ? 'large' : undefined))
const tall = computed(() => (props.barSize === 'tall' ? 'tall' : undefined))

const cls = computed(() => ['ss-window', 'ss-recede', props.className, props.class])

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
  <!-- Terminal chrome -->
  <div
    v-if="props.chrome === 'terminal'"
    v-bind="$attrs"
    :class="cls"
    data-chrome="terminal"
    :data-lights="props.lights === 'grey' ? 'grey' : undefined"
    :data-lights-size="large"
    :data-receded="props.receded || undefined"
    :style="props.style"
  >
    <div class="ss-window__bar">
      <span class="ss-window__lights">
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
      </span>
      <span v-if="hasTitle" class="ss-term__title">
        <slot name="title">{{ props.title }}</slot>
      </span>
    </div>
    <div :class="['ss-window__body', 'ss-term', props.body?.className, props.body?.class]" v-bind="props.body">
      <slot />
    </div>
  </div>

  <!-- Glass / Card / Hairline chrome -->
  <div
    v-else-if="props.chrome === 'glass' || props.chrome === 'card' || props.chrome === 'hairline'"
    v-bind="$attrs"
    :class="cls"
    :data-chrome="props.chrome"
    :data-lights="props.lights === 'color' || props.lights === 'white' ? props.lights : props.chrome === 'glass' ? 'grey' : undefined"
    :data-receded="props.receded || undefined"
    :style="props.style"
  >
    <div class="ss-window__bar">
      <span class="ss-window__lights">
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
      </span>
      <span v-if="hasUrl" class="ss-window__url">
        <svg v-if="props.chrome === 'glass'" class="ss-window__lock" width="7" height="8" viewBox="0 0 7 8" aria-hidden="true">
          <path d="M1.5 3.3V2.4a2 2 0 0 1 4 0v.9" fill="none" stroke="currentColor" stroke-width="1.1" />
          <rect x="0" y="3.3" width="7" height="4.7" rx="1.2" fill="currentColor" />
        </svg>
        <span class="ss-window__url-text">
          <slot name="url">
            <component :is="asComponent(props.url)" v-if="isRenderableObject(props.url)" />
            <template v-else>{{ props.url }}</template>
          </slot>
        </span>
      </span>
      <span class="ss-window__end">
        <slot name="toolbar">
          <component :is="asComponent(props.toolbar)" v-if="isRenderableObject(props.toolbar)" />
          <template v-else>{{ props.toolbar }}</template>
        </slot>
      </span>
    </div>
    <div :class="['ss-window__body', props.body?.className, props.body?.class]" v-bind="props.body">
      <slot />
    </div>
  </div>

  <!-- Sidebar app -->
  <div
    v-else-if="hasSidebar"
    v-bind="$attrs"
    :class="cls"
    data-kind="sidebar"
    :data-side="props.sidebarStyle === 'floating' ? 'floating' : undefined"
    :data-lights="props.lights === 'grey' ? 'grey' : undefined"
    :data-lights-size="large"
    :data-bar="tall"
    :data-receded="props.receded || undefined"
    :data-url-shape="props.urlShape"
    :style="props.style"
  >
    <aside class="ss-window__side" :style="{ width: `${props.sidebarWidth}px` }">
      <div class="ss-window__side-top">
        <span class="ss-window__lights">
          <span class="ss-window__dot" />
          <span class="ss-window__dot" />
          <span class="ss-window__dot" />
        </span>
      </div>
      <slot name="sidebar">
        <component :is="asComponent(props.sidebar)" v-if="isRenderableObject(props.sidebar)" />
        <template v-else>{{ props.sidebar }}</template>
      </slot>
    </aside>
    <div class="ss-window__main">
      <div class="ss-window__bar">
        <span v-if="hasTitle" class="ss-window__heading">
          <slot name="title">{{ props.title }}</slot>
        </span>
        <slot v-if="hasLead" name="lead">
          <component :is="asComponent(props.lead)" v-if="isRenderableObject(props.lead)" />
          <template v-else>{{ props.lead }}</template>
        </slot>
        <template v-if="hasUrl">
          <span v-if="props.nav" class="ss-window__nav">
            <svg class="ss-window__chev" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
              <path d="M6.5 1.5 3 5l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg class="ss-window__chev" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
              <path d="M3.5 1.5 7 5 3.5 8.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
          <span class="ss-window__url">
            <slot name="url">
              <component :is="asComponent(props.url)" v-if="isRenderableObject(props.url)" />
              <template v-else>{{ props.url }}</template>
            </slot>
          </span>
        </template>
        <span class="ss-window__spacer" />
        <slot v-if="hasToolbar" name="toolbar">
          <component :is="asComponent(props.toolbar)" v-if="isRenderableObject(props.toolbar)" />
          <template v-else>{{ props.toolbar }}</template>
        </slot>
      </div>
      <div :class="['ss-window__body', props.body?.className, props.body?.class]" v-bind="props.body">
        <slot />
      </div>
    </div>
  </div>

  <!-- Tabs app -->
  <div
    v-else-if="hasTabs"
    v-bind="$attrs"
    :class="cls"
    data-kind="tabs"
    :data-lights="props.lights === 'grey' ? 'grey' : undefined"
    :data-lights-size="large"
    :data-receded="props.receded || undefined"
    :data-url-shape="props.urlShape"
    :style="props.style"
  >
    <div class="ss-window__tabs">
      <span class="ss-window__lights">
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
      </span>
      <span
        v-for="(t, i) in props.tabs"
        :key="i"
        class="ss-window__tab"
        :data-active="i === 0 || undefined"
      >
        <span class="ss-window__favicon" />
        <span class="ss-window__tab-label">
          <component :is="asComponent(t)" v-if="isRenderableObject(t)" />
          <template v-else>{{ t }}</template>
        </span>
      </span>
    </div>
    <div class="ss-window__bar">
      <template v-if="hasUrl">
        <span v-if="props.nav" class="ss-window__nav">
          <svg class="ss-window__chev" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M6.5 1.5 3 5l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <svg class="ss-window__chev" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M3.5 1.5 7 5 3.5 8.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="ss-window__url">
          <slot name="url">
            <component :is="asComponent(props.url)" v-if="isRenderableObject(props.url)" />
            <template v-else>{{ props.url }}</template>
          </slot>
        </span>
      </template>
      <slot v-if="hasToolbar" name="toolbar">
        <component :is="asComponent(props.toolbar)" v-if="isRenderableObject(props.toolbar)" />
        <template v-else>{{ props.toolbar }}</template>
      </slot>
    </div>
    <div :class="['ss-window__body', props.body?.className, props.body?.class]" v-bind="props.body">
      <slot />
    </div>
  </div>

  <!-- Standard Window (browser / app) -->
  <div
    v-else
    v-bind="$attrs"
    :class="cls"
    :data-receded="props.receded || undefined"
    :data-url-shape="props.urlShape"
    :data-lights="props.lights === 'grey' ? 'grey' : undefined"
    :data-lights-size="large"
    :data-bar="tall"
    :style="props.style"
  >
    <div class="ss-window__bar">
      <span class="ss-window__lights">
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
        <span class="ss-window__dot" />
      </span>
      <template v-if="hasUrl">
        <span v-if="props.nav" class="ss-window__nav">
          <svg class="ss-window__chev" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M6.5 1.5 3 5l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <svg class="ss-window__chev" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M3.5 1.5 7 5 3.5 8.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="ss-window__url">
          <slot name="url">
            <component :is="asComponent(props.url)" v-if="isRenderableObject(props.url)" />
            <template v-else>{{ props.url }}</template>
          </slot>
        </span>
      </template>
      <span v-if="hasTitle" class="ss-window__title" :data-toolbar="hasToolbar ? true : undefined">
        <slot name="title">{{ props.title }}</slot>
      </span>
      <slot v-if="hasLead" name="lead">
        <component :is="asComponent(props.lead)" v-if="isRenderableObject(props.lead)" />
        <template v-else>{{ props.lead }}</template>
      </slot>
      <span v-if="!hasUrl && !hasTitle" class="ss-window__spacer" />
      <slot v-if="hasToolbar" name="toolbar">
        <component :is="asComponent(props.toolbar)" v-if="isRenderableObject(props.toolbar)" />
        <template v-else>{{ props.toolbar }}</template>
      </slot>
    </div>
    <div :class="['ss-window__body', props.body?.className, props.body?.class]" v-bind="props.body">
      <slot />
    </div>
  </div>
</template>
