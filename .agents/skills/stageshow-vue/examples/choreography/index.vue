<script lang="ts">
import { defineComponent, h, onBeforeUnmount, onMounted, ref, type CSSProperties } from 'vue'
import { Icon, Stage, type Act } from '../../kit'
import './choreography.css'

type Locale = { country: string; currency: string; price: string; method: string; fields: { label: string; value: string; half?: boolean }[] }
const locales: Locale[] = [
  { country: 'United States', currency: 'USD', price: '$38.00', method: 'Card', fields: [
    { label: 'Name', value: 'Alex Morgan' }, { label: 'Street address', value: '24 Maple Avenue' }, { label: 'City', value: 'Portland', half: true }, { label: 'ZIP code', value: '97205', half: true },
  ] },
  { country: 'Germany', currency: 'EUR', price: '€35.00', method: 'Bank transfer', fields: [
    { label: 'Name', value: 'Alex Morgan' }, { label: 'Street and number', value: 'Lindenstraße 18' }, { label: 'Postcode', value: '10115', half: true }, { label: 'City', value: 'Berlin', half: true },
  ] },
  { country: 'Canada', currency: 'CAD', price: 'CA$52.00', method: 'Card', fields: [
    { label: 'Name', value: 'Alex Morgan' }, { label: 'Street address', value: '18 Cedar Lane' }, { label: 'City', value: 'Victoria', half: true }, { label: 'Province', value: 'BC', half: true }, { label: 'Postal code', value: 'V8V 1A1' },
  ] },
]

type State = { locale: number }
const initial: State = { locale: 0 }
const poster: State = { locale: 2 }

// Starts overlap. The currency identifies the change before the dependent
// price, payment method and address respond. The final destination holds.
export async function localeSequence(a: Act<State>) {
  await a.wait(1600)
  a.mark('germany')
  await a.set({ locale: 1 })
  await a.wait(3300)
  a.mark('canada')
  await a.set({ locale: 2 })
  await a.wait(2900)
}

function useWidth(initialWidth: number) {
  const elRef = ref<HTMLDivElement | null>(null)
  const width = ref(initialWidth)
  let observer: ResizeObserver | null = null
  onMounted(() => {
    const node = elRef.value
    if (!node) return
    const measure = () => { if (node.clientWidth) width.value = node.clientWidth }
    measure()
    observer = new ResizeObserver(measure)
    observer.observe(node)
  })
  onBeforeUnmount(() => {
    observer?.disconnect()
  })
  return [elRef, width] as const
}

function renderBank() {
  return h(
    'svg',
    {
      width: '14',
      height: '14',
      viewBox: '0 0 14 14',
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': '1.25',
      'stroke-linejoin': 'round',
      'aria-hidden': 'true',
    },
    [h('path', { d: 'm2 4 5-2 5 2v1H2ZM3.5 6.5v3M7 6.5v3M10.5 6.5v3M2 11.5h10' })],
  )
}

function renderPrice(locale: number) {
  return h('span', { class: 'cy-roll cy-price', 'aria-label': locales[locale].price }, [
    h(
      'span',
      { class: 'cy-vertical-track', 'aria-hidden': 'true' },
      locales.map((item) => h('span', { class: 'cy-roll-row', key: item.country }, item.price)),
    ),
  ])
}

export const Checkout = defineComponent({
  name: 'Checkout',
  props: {
    locale: { type: Number, required: true },
    width: { type: Number, required: true },
    good: { type: Boolean, default: true },
    top: { type: Number, default: 24 },
    wide: { type: Boolean, default: false },
  },
  setup(props) {
    return () =>
      h(
        'div',
        {
          class: 'cy-checkout',
          'data-coordinated': props.good || undefined,
          'data-locale': props.locale,
          'data-layout': props.wide ? 'wide' : 'compact',
          style: {
            width: `${props.width - 32}px`,
            height: '420px',
            left: '16px',
            top: `${props.top}px`,
            '--cy-index': props.locale,
          } as CSSProperties,
        },
        [
          h('aside', { class: 'cy-order' }, [
            h('span', { class: 'cy-summary-heading' }, 'Order summary'),
            h('span', { class: 'cy-notebook', 'aria-hidden': 'true' }, [
              h('i'),
              h('b', ['FIELD', h('br'), 'JOURNAL']),
            ]),
            h('div', { class: 'cy-product' }, [
              h('strong', 'Field journal'),
              h('span', 'Olive · dotted pages'),
              h('span', { class: 'cy-quantity' }, 'Quantity 1'),
            ]),
            h('div', { class: 'cy-total' }, [h('span', 'Total'), renderPrice(props.locale)]),
          ]),
          h('div', { class: 'cy-body' }, [
            h('div', { class: 'cy-form-heading' }, 'Delivery details'),
            h('div', { class: 'cy-locale' }, [
              h('span', 'Ship to'),
              h(
                'span',
                {
                  class: 'cy-roll cy-currency',
                  'aria-label': `${locales[props.locale].country}, ${locales[props.locale].currency}`,
                },
                [
                  h(
                    'span',
                    { class: 'cy-vertical-track', 'aria-hidden': 'true' },
                    locales.map((item) =>
                      h('span', { class: 'cy-roll-row', key: item.country }, [
                        item.country,
                        h('b', '·'),
                        item.currency,
                      ]),
                    ),
                  ),
                ],
              ),
            ]),
            h('div', { class: 'cy-method' }, [
              h('span', { class: 'cy-label' }, 'Payment method'),
              h('div', { class: 'cy-method-control' }, [
                h('span', { class: 'cy-roll cy-method-icon' }, [
                  h(
                    'span',
                    { class: 'cy-vertical-track', 'aria-hidden': 'true' },
                    locales.map((item) =>
                      h('span', { class: 'cy-roll-row', key: item.country }, [
                        item.method === 'Card' ? h(Icon, { name: 'card', size: 14 }) : renderBank(),
                      ]),
                    ),
                  ),
                ]),
                h(
                  'span',
                  { class: 'cy-roll cy-method-name', 'aria-label': locales[props.locale].method },
                  [
                    h(
                      'span',
                      { class: 'cy-vertical-track', 'aria-hidden': 'true' },
                      locales.map((item) => h('span', { class: 'cy-roll-row', key: item.country }, item.method)),
                    ),
                  ],
                ),
                h(Icon, { name: 'chevron-down', size: 12 }),
              ]),
            ]),
            h('div', { class: 'cy-address-viewport', 'data-crop': '' }, [
              h(
                'div',
                { class: 'cy-address-track' },
                locales.map((item, index) =>
                  h(
                    'div',
                    { class: 'cy-address', key: item.country, 'aria-hidden': index !== props.locale },
                    item.fields.map((field) =>
                      h(
                        'div',
                        { class: 'cy-field', key: field.label, 'data-half': field.half || undefined },
                        [
                          h('span', { class: 'cy-label' }, field.label),
                          h('span', { class: 'cy-field-value' }, field.value),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ]),
            h('div', { class: 'cy-footer' }, [
              h('div', { class: 'cy-pay' }, [
                h(
                  'span',
                  { class: 'cy-roll cy-pay-label', 'aria-label': `Pay ${locales[props.locale].price}` },
                  [
                    h(
                      'span',
                      { class: 'cy-vertical-track', 'aria-hidden': 'true' },
                      locales.map((item) =>
                        h('span', { class: 'cy-roll-row', key: item.country }, `Pay ${item.price}`),
                      ),
                    ),
                  ],
                ),
                h(Icon, { name: 'lock', size: 12 }),
              ]),
              h('span', 'Shipping included'),
            ]),
          ]),
        ],
      )
  },
})

export const choreographyLessons = [{
  id: 'dependent-starts', title: 'Related changes overlap', note: 'The same checkout, curve and duration. On the right, currency leads price, then payment method and address. Watch the outer frame and Pay button stay in place.', bad: 'Every layer starts together', good: 'Dependent responses overlap',
}] as const

export const ChoreographyComparison = defineComponent({
  name: 'ChoreographyComparison',
  props: {
    lessonId: { type: String, default: 'dependent-starts' },
  },
  setup(props) {
    const [hostRef, width] = useWidth(704)
    const revision = ref(0)
    return () => {
      if (props.lessonId !== 'dependent-starts') return null
      const w = width.value
      const stacked = w < 620
      const cell = stacked ? w : (w - 24) / 2
      return h('section', { class: 'cy-comparison' }, [
        h('header', [
          h('div', [
            h('h2', choreographyLessons[0].title),
            h('p', choreographyLessons[0].note),
          ]),
          h(
            'button',
            {
              type: 'button',
              class: 'tc-replay',
              onClick: () => {
                revision.value++
              },
            },
            'Replay pair',
          ),
        ]),
        h('div', { ref: hostRef, class: 'cy-pair-host' }, [
          h(
            Stage,
            {
              key: revision.value,
              width: w,
              height: stacked ? 976 : 476,
              initial,
              poster,
              play: 'once',
              script: localeSequence,
            },
            {
              default: ({ state }: { state: State }) =>
                h(
                  'div',
                  { class: 'cy-pair' },
                  [false, true].map((good, i) =>
                    h(
                      'div',
                      {
                        key: String(good),
                        class: 'cy-pair-cell',
                        style: {
                          width: `${cell}px`,
                          left: `${stacked ? 0 : i * (cell + 24)}px`,
                          top: `${stacked ? i * 500 : 0}px`,
                        },
                      },
                      [
                        h(
                          'span',
                          { class: 'cy-pair-label' },
                          good ? choreographyLessons[0].good : choreographyLessons[0].bad,
                        ),
                        h(Checkout, { locale: state.locale, width: cell, good, top: 40 }),
                      ],
                    ),
                  ),
                ),
            },
          ),
        ]),
      ])
    }
  },
})
</script>

<script setup lang="ts">
const [demoRef, width] = useWidth(288)
</script>

<template>
  <div ref="demoRef" class="cy-demo">
    <Stage
      :width="width"
      :height="468"
      :initial="initial"
      :poster="poster"
      play="once"
      :script="localeSequence"
      v-slot="{ state }"
    >
      <div class="cy-scene">
        <Checkout :locale="state.locale" :width="width" :wide="width >= 560" />
      </div>
    </Stage>
  </div>
</template>
