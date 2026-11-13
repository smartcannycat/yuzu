<script lang="ts">
import { defineComponent, h } from 'vue'
import { Icon } from '../../kit'
import './studies.css'

// These are quiet, static product studies. Their anatomy changes with the
// product; tokens alone cannot turn an invitation form into a finance tool.

export const ConsoleLook = defineComponent({
  name: 'ConsoleLook',
  setup() {
    return () =>
      h('div', { class: 'lk-product lk-console' }, [
        h('header', { class: 'lk-product-head' }, [
          h('span', { class: 'lk-console-command' }, '>_'),
          h('strong', 'Deployments'),
          h('span', { class: 'lk-console-env' }, 'production'),
        ]),
        h('div', { class: 'lk-console-body' }, [
          h('div', { class: 'lk-console-title' }, [
            h('strong', 'account-web'),
            h('span', [h('i'), 'Ready']),
          ]),
          h('div', { class: 'lk-console-commit' }, [
            h('code', '8f2c19a'),
            h('span', 'Update account settings'),
          ]),
          h('div', { class: 'lk-console-log' }, [
            h('div', [h(Icon, { name: 'check', size: 12 }), h('span', 'Build application'), h('span', '5s')]),
            h('div', [h(Icon, { name: 'check', size: 12 }), h('span', 'Run checks'), h('span', '2s')]),
            h('div', [h(Icon, { name: 'check', size: 12 }), h('span', 'Publish'), h('span', '2s')]),
          ]),
          h('div', { class: 'lk-console-footer' }, [
            h('span', 'Built in 9 seconds'),
            h('span', ['View deployment ', h(Icon, { name: 'external', size: 13 })]),
          ]),
        ]),
      ])
  },
})

export const FinanceLook = defineComponent({
  name: 'FinanceLook',
  setup() {
    return () =>
      h('div', { class: 'lk-product lk-finance' }, [
        h('header', { class: 'lk-product-head' }, [
          h('strong', 'Overview'),
          h('span', { class: 'lk-finance-period' }, ['This month ', h(Icon, { name: 'chevron-down', size: 12 })]),
        ]),
        h('div', { class: 'lk-finance-body' }, [
          h('div', { class: 'lk-finance-label' }, 'Total balance'),
          h('div', { class: 'lk-finance-balance' }, ['$48,250', h('span', '.00')]),
          h('div', { class: 'lk-finance-trend' }, ['+4.8% ', h('span', 'from last month')]),
          h(
            'svg',
            {
              class: 'lk-finance-chart',
              viewBox: '0 0 276 60',
              role: 'img',
              'aria-label': 'Balance increased steadily during the month',
            },
            [
              h('path', { class: 'lk-finance-grid', d: 'M0 52.5H276M0 24.5H276' }),
              h('path', {
                class: 'lk-finance-area',
                d: 'M0 49C14 49 15 44 28 45S42 37 55 39S68 42 82 34S97 35 110 29S125 32 138 25S152 28 166 20S179 23 193 16S207 18 221 11S235 15 248 7S263 9 276 3V60H0Z',
              }),
              h('path', {
                class: 'lk-finance-line',
                d: 'M0 49C14 49 15 44 28 45S42 37 55 39S68 42 82 34S97 35 110 29S125 32 138 25S152 28 166 20S179 23 193 16S207 18 221 11S235 15 248 7S263 9 276 3',
              }),
            ],
          ),
          h('div', { class: 'lk-finance-account' }, [
            h('span', { class: 'lk-finance-account-icon' }, [h(Icon, { name: 'card', size: 15 })]),
            h('span', ['Operating', h('span', '•• 4829')]),
            h('strong', '$36,250.00'),
          ]),
          h('div', { class: 'lk-finance-account' }, [
            h('span', { class: 'lk-finance-account-icon' }, [h(Icon, { name: 'lock', size: 15 })]),
            h('span', ['Reserve', h('span', '•• 9012')]),
            h('strong', '$12,000.00'),
          ]),
        ]),
      ])
  },
})

export const CanvasLook = defineComponent({
  name: 'CanvasLook',
  setup() {
    return () =>
      h('div', { class: 'lk-product lk-canvas' }, [
        h('header', { class: 'lk-product-head' }, [
          h('strong', 'Untitled canvas'),
          h('span', ['100% ', h(Icon, { name: 'chevron-down', size: 12 })]),
        ]),
        h('div', { class: 'lk-canvas-workspace' }, [
          h('div', { class: 'lk-canvas-tools', 'aria-hidden': 'true' }, [
            h('span', { class: 'lk-canvas-tool-selected' }, [
              h('svg', { viewBox: '0 0 16 16' }, [h('path', { d: 'm4 2 9 6-5 1-2 4Z' })]),
            ]),
            h('span', [
              h('svg', { viewBox: '0 0 16 16' }, [h('rect', { x: '3', y: '3', width: '10', height: '10', rx: '1' })]),
            ]),
            h('span', { class: 'lk-canvas-type' }, 'T'),
          ]),
          h('div', { class: 'lk-canvas-art', 'aria-label': 'Selected blue geometric poster' }, [
            h('div', { class: 'lk-canvas-art-title' }, ['A new', h('br'), 'perspective.']),
            h('svg', { class: 'lk-canvas-shape', viewBox: '0 0 160 110', 'aria-hidden': 'true' }, [
              h('path', { d: 'M14 94 71 8 137 94Z' }),
              h('path', { d: 'm48 94 39-61 47 61' }),
            ]),
            h('span', { class: 'lk-canvas-art-footer' }, 'FORM / 01'),
            h('i'),
            h('i'),
            h('i'),
            h('i'),
          ]),
          h('span', { class: 'lk-canvas-size' }, '152 × 184'),
          h('div', { class: 'lk-canvas-properties' }, [
            h('span', [h('i'), 'Fill']),
            h('strong', '#2E55CC'),
            h('span', '100%'),
          ]),
        ]),
      ])
  },
})

export const MessagesLook = defineComponent({
  name: 'MessagesLook',
  setup() {
    return () =>
      h('div', { class: 'lk-product lk-messages' }, [
        h('header', { class: 'lk-product-head' }, [
          h('span', { class: 'lk-message-avatar' }, 'AL'),
          h('span', { class: 'lk-message-person' }, [h('strong', 'Alex Lee'), h('span', 'Design team')]),
          h(Icon, { name: 'more', size: 16 }),
        ]),
        h('div', { class: 'lk-message-thread' }, [
          h('div', { class: 'lk-message-time' }, 'Today, 10:42'),
          h('div', { class: 'lk-message-in' }, ['The new cover is ready.', h('br'), 'What do you think?']),
          h('div', { class: 'lk-message-file' }, [
            h('span', [h(Icon, { name: 'file', size: 17 })]),
            h('span', [h('strong', 'Cover exploration.pdf'), h('small', '2 pages · 1.4 MB')]),
          ]),
          h('div', { class: 'lk-message-out' }, 'This is the one. Let’s share it.'),
          h('div', { class: 'lk-message-read' }, ['Seen ', h(Icon, { name: 'check', size: 11 })]),
        ]),
        h('div', { class: 'lk-message-composer' }, [
          h(Icon, { name: 'plus', size: 15 }),
          h('span', 'Write a message…'),
          h('span', { class: 'lk-message-send' }, [h(Icon, { name: 'arrow', size: 13 })]),
        ]),
      ])
  },
})

export const ResearchLook = defineComponent({
  name: 'ResearchLook',
  setup() {
    return () =>
      h('div', { class: 'lk-product lk-research' }, [
        h('header', { class: 'lk-product-head' }, [
          h(Icon, { name: 'file', size: 14 }),
          h('span', 'Research / Field notes'),
          h(Icon, { name: 'more', size: 16 }),
        ]),
        h('div', { class: 'lk-research-body' }, [
          h('div', { class: 'lk-research-kicker' }, ['PRODUCT RESEARCH ', h('span', '06')]),
          h('div', { class: 'lk-research-title' }, ['Make room', h('br'), 'for the first idea.']),
          h('p', ['The best tools get out of the way.', h('br'), 'Start with space, then add structure.']),
          h('div', { class: 'lk-research-note' }, [
            h('span', '01'),
            h('div', [h('strong', 'A quieter starting point'), h('p', 'Less setup. More time to explore.')]),
          ]),
          h('div', { class: 'lk-research-source' }, [
            h('span', 'Interview notes'),
            h('span', ['4 sources ', h(Icon, { name: 'arrow', size: 12 })]),
          ]),
        ]),
      ])
  },
})
</script>

<script setup lang="ts">
withDefaults(
  defineProps<{
    kind?: 'console' | 'finance' | 'canvas' | 'messages' | 'research'
  }>(),
  {
    kind: 'console',
  },
)
</script>

<template>
  <ConsoleLook v-if="kind === 'console'" />
  <FinanceLook v-else-if="kind === 'finance'" />
  <CanvasLook v-else-if="kind === 'canvas'" />
  <MessagesLook v-else-if="kind === 'messages'" />
  <ResearchLook v-else />
</template>
