<script lang="ts">
import { defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Connector, Icon, Stage, States, type Act, type Rect } from '../../kit'
import './composed.css'

// The compact output detours around the incoming routes. Keep this one path,
// rather than drawing separate segments simultaneously. Its arrow follows the
// real transition completion, including a paused host and reduced motion.
const UsageDelivery = defineComponent({
  name: 'UsageDelivery',
  props: {
    path: { type: String, required: true },
    to: { type: Object as () => { x: number; y: number }, required: true },
    show: { type: Boolean, required: true },
  },
  setup(props) {
    const line = ref<SVGPathElement | null>(null)
    const arrived = ref(false)
    let cleanup: (() => void) | null = null

    function setupListener() {
      cleanup?.()
      cleanup = null
      const element = line.value
      arrived.value = false
      if (!element || !props.show) return
      const check = () => {
        if (Math.abs(parseFloat(getComputedStyle(element).strokeDashoffset)) < 0.0001) arrived.value = true
      }
      const finish = (event: TransitionEvent) => {
        if (event.target === element && event.propertyName === 'stroke-dashoffset') check()
      }
      element.addEventListener('transitionend', finish)
      element.addEventListener('transitioncancel', finish)
      check()
      cleanup = () => {
        element.removeEventListener('transitionend', finish)
        element.removeEventListener('transitioncancel', finish)
      }
    }

    onMounted(() => {
      setupListener()
    })

    watch(
      () => [props.path, props.show],
      () => {
        setupListener()
      },
      { flush: 'post' },
    )

    onBeforeUnmount(() => {
      cleanup?.()
    })

    return () => {
      const arrow = `M${props.to.x + 6} ${props.to.y - 4}L${props.to.x} ${props.to.y}L${props.to.x + 6} ${props.to.y + 4}`
      return h(
        'svg',
        {
          class: 'ss-connector an-usage-delivery',
          'data-show': props.show || undefined,
          'data-arrived': (props.show && arrived.value) || undefined,
          'aria-hidden': 'true',
        },
        [
          h('path', { ref: line, class: 'ss-connector__line', d: props.path, pathLength: '1' }),
          h('path', { class: 'ss-connector__arrow', d: arrow }),
        ],
      )
    }
  },
})

type Collection = { phase: number }
async function collectUsage(a: Act<Collection>) {
  a.mark('start'); await a.wait(850)
  await a.move({ at: 'sync-usage', x: 0.92, y: 0.85 }); await a.click()
  a.mark('collect'); await a.set({ phase: 1 })
  await a.move('usage-rest', { duration: 350 }); await a.wait(750)
  a.mark('post'); await a.set({ phase: 2 }); await a.wait(1100)
  a.mark('invoice'); await a.set({ phase: 3 })
  await a.wait(3050); a.mark('done')
  // The first invoice update is complete; its three live sources stay connected.
}

/** Three live usage sources feed one invoice; the junction is an aggregation,
 * not a fourth decorative service. The result waits for the final delivery. */
export const CollectionStudy = defineComponent({
  name: 'CollectionStudy',
  props: {
    width: { type: Number, required: true },
  },
  setup(props) {
    const rows = [
      { name: 'API requests', meter: 'API calls', value: '24.8k', amount: '$124.00', colour: '#3478e5' },
      { name: 'Storage', meter: 'Storage', value: '18.2 GB', amount: '$18.20', colour: '#3478e5' },
      { name: 'Background jobs', meter: 'Jobs', value: '312', amount: '$46.80', colour: '#3478e5' },
    ]
    return () => {
      const width = props.width
      const compact = width < 520
      return h(
        Stage,
        {
          width,
          height: compact ? 636 : 464,
          initial: { phase: 0 },
          poster: { phase: 3 },
          script: collectUsage,
          play: 'once',
          cursor: { at: { x: 24, y: compact ? 378 : 440 } },
          greys: 'cool',
          accent: '#3478e5',
          class: 'an-study an-collection',
        },
        {
          default: ({ state: s, rect }: { state: Collection; rect: (name: string) => Rect }) => {
            const sources = rows.map((_, i) => rect(`usage-source-${i}`))
            const invoice = rect('usage-invoice')
            const field = rect('usage-invoice-field')
            const junction = { x: sources[1].x + sources[1].width + 24, y: sources[1].y + sources[1].height / 2 }
            const destination = { x: invoice.x + invoice.width, y: field.y + field.height / 2 }
            const ready = sources.every((r) => r.width > 0) && invoice.width > 0 && field.width > 0
            const outer = width - 16
            const radius = 6
            const direction = destination.y > junction.y ? 1 : -1
            const delivery = `M${junction.x} ${junction.y}H${outer - radius}Q${outer} ${junction.y} ${outer} ${junction.y + direction * radius}V${destination.y - direction * radius}Q${outer} ${destination.y} ${outer - radius} ${destination.y}H${destination.x}`

            return h(
              'div',
              { class: 'an-collection-scene', 'data-live': s.phase >= 1 || undefined },
              [
                h(
                  'section',
                  {
                    class: 'an-usage-invoice',
                    'data-target': 'usage-invoice',
                    style: compact
                      ? { left: '16px', top: '28px', width: `${width - 52}px` }
                      : { left: '28px', top: '108px', width: `${width - 252}px` },
                  },
                  [
                    h('header', [h('strong', 'Invoice'), h('span', '#0084 · October 2026')]),
                    h('div', { class: 'an-invoice-recipient' }, [h('span', 'Bill to'), h('strong', 'Coast workspace')]),
                    h('div', { class: 'an-invoice-balance' }, [
                      h('div', { class: 'an-invoice-balance-head', 'data-target': 'usage-invoice-field' }, [
                        h('span', 'Amount due'),
                        h('span', { class: 'an-invoice-live' }, [
                          h('i', { class: 'an-invoice-status-dot', 'data-ready': s.phase === 3 || undefined }),
                          h(States, {
                            align: 'start',
                            value: s.phase === 3 ? 'ready' : 'waiting',
                            states: { waiting: 'Awaiting usage', ready: 'Live usage' },
                          }),
                        ]),
                      ]),
                      h('div', { class: 'an-invoice-total' }, [
                        h(States, {
                          align: 'start',
                          value: s.phase === 3 ? 'amount' : 'empty',
                          states: { empty: '$0.00', amount: '$189.00' },
                        }),
                      ]),
                    ]),
                    h(
                      'div',
                      { class: 'an-invoice-lines' },
                      rows.map((row) =>
                        h('div', { key: row.name }, [
                          h('span', row.name),
                          h(States, {
                            align: 'end',
                            value: s.phase === 3 ? 'amount' : 'empty',
                            states: { empty: '—', amount: row.amount },
                          }),
                        ]),
                      ),
                    ),
                  ],
                ),
                h(
                  'section',
                  {
                    class: 'an-usage-monitor',
                    style: compact
                      ? { left: '16px', top: '400px', width: `${Math.min(228, width - 92)}px` }
                      : { left: `${width - 278}px`, top: '28px', width: '228px' },
                  },
                  [
                    h('header', [h('strong', 'Usage'), h('span', 'October')]),
                    h(
                      'div',
                      { class: 'an-usage-sources' },
                      rows.map((row, i) =>
                        h('div', { class: 'an-usage-source', 'data-target': `usage-source-${i}`, key: row.name }, [
                          h('span', [h('i', { class: 'an-source-cue', style: { background: row.colour } }), row.meter]),
                          h('strong', row.value),
                        ]),
                      ),
                    ),
                    h('div', { class: 'an-usage-sync', 'data-target': 'sync-usage', 'data-cursor': 'hand' }, [
                      h(States, {
                        value: s.phase === 0 ? 'idle' : s.phase < 3 ? 'busy' : 'done',
                        states: { idle: 'Connect', busy: 'Connecting…', done: 'Connected' },
                      }),
                    ]),
                  ],
                ),
                ...sources.map((source, i) =>
                  h(Connector, {
                    key: i,
                    class: `an-usage-feed an-fine-dotted an-usage-feed--${i}`,
                    from: { x: source.x + source.width, y: source.y + source.height / 2 },
                    to: junction,
                    route: 'h',
                    radius: 6,
                    dashed: true,
                    dots: 'none',
                    show: ready && s.phase >= 1,
                  }),
                ),
                h(UsageDelivery, { path: delivery, to: destination, show: ready && s.phase >= 2 }),
                h(
                  'svg',
                  { class: 'an-usage-junction', 'data-visible': (ready && s.phase >= 2) || undefined, 'aria-hidden': 'true' },
                  [h('circle', { cx: junction.x, cy: junction.y, r: '3' })],
                ),
                h('span', {
                  class: 'an-composed-rest',
                  'data-target': 'usage-rest',
                  style: { left: `${compact ? 16 : width - 74}px`, top: `${compact ? 369 : 290}px` },
                }),
              ],
            )
          },
        },
      )
    }
  },
})

type Detail = { phase: number; selected: boolean; clearing: boolean }
async function inspectPayout(a: Act<Detail>) {
  a.mark('start'); await a.wait(850)
  await a.move({ at: 'payout-row', x: 0.2, y: 0.5 }); await a.click()
  a.mark('link'); await a.set({ selected: true, phase: 1 })
  await a.move('payout-rest', { duration: 350 }); await a.wait(750)
  a.mark('detail'); await a.set({ phase: 2 }); await a.wait(920)
  a.mark('leader'); await a.set({ phase: 3 }); await a.wait(1100)
  a.mark('explanation'); await a.set({ phase: 4 }); await a.wait(2300)
  await a.move('clear-payout'); await a.click(); a.mark('clear')
  await a.set({ clearing: true }); await a.wait(400)
  await a.set({ selected: false, clearing: false, phase: 0 }); await a.wait(600); a.mark('done')
}

/** A linked record and a field explanation use different line treatments.
 * The payout list remains the main product view through the entire story. */
export const DetailStudy = defineComponent({
  name: 'DetailStudy',
  props: {
    width: { type: Number, required: true },
  },
  setup(props) {
    return () => {
      const width = props.width
      const compact = width < 520
      return h(
        Stage,
        {
          width,
          height: compact ? 600 : 436,
          initial: { phase: 0, selected: false, clearing: false },
          poster: { phase: 4, selected: true, clearing: false },
          script: inspectPayout,
          play: 'once',
          cursor: { at: { x: width - 24, y: compact ? 574 : 410 } },
          greys: 'cool',
          accent: '#326be6',
          class: 'an-study an-detail',
        },
        {
          default: ({ state: s, rect }: { state: Detail; rect: (name: string) => Rect }) => {
            const row = rect('payout-row')
            const detail = rect('settlement-detail')
            const note = rect('arrival-note')
            const from = { x: row.x + row.width / 2, y: row.y + row.height }
            const to = compact
              ? { x: detail.x + detail.width / 2, y: detail.y }
              : { x: detail.x + detail.width, y: detail.y + detail.height - 34 }
            const leaderFrom = { x: detail.x + detail.width / 2, y: detail.y + detail.height }
            const leaderTo = { x: note.x + note.width / 2, y: note.y }
            const measured = row.width > 0 && detail.width > 0 && note.width > 0 && !s.clearing

            return h(
              'div',
              { class: 'an-detail-scene', 'data-transmitting': s.phase === 1 || undefined },
              [
                h(
                  'section',
                  {
                    class: 'an-payout-panel',
                    style: compact
                      ? { left: '16px', top: '28px', width: `${width - 32}px` }
                      : { left: '244px', top: '28px', width: `${width - 272}px` },
                  },
                  [
                    h('header', [
                      h('div', [h('strong', 'Payouts'), h('span', 'Checking •0814')]),
                      h('span', { 'data-target': 'clear-payout', 'data-cursor': 'hand' }, 'Clear detail'),
                    ]),
                    h('div', { class: 'an-payout-columns' }, [h('span', 'Created'), h('span', 'Amount')]),
                    h('div', { class: 'an-payout-row' }, [h('span', ['Oct 18 ', h('small', 'Paid')]), h('strong', '$740.00')]),
                    h('div', { class: 'an-payout-row' }, [h('span', ['Oct 22 ', h('small', 'Paid')]), h('strong', '$920.00')]),
                    h(
                      'div',
                      {
                        class: 'an-payout-row',
                        'data-target': 'payout-row',
                        'data-cursor': 'hand',
                        'data-selected': s.selected || undefined,
                      },
                      [h('span', ['Today ', h('small', 'Scheduled')]), h('strong', '$1,284.60')],
                    ),
                  ],
                ),
                h(
                  'section',
                  {
                    class: 'an-settlement-detail',
                    'data-target': 'settlement-detail',
                    'data-visible': (s.phase >= 2 && !s.clearing) || undefined,
                    style: compact
                      ? { left: '32px', top: '314px', width: `${width - 64}px` }
                      : { left: '28px', top: '150px', width: '224px' },
                  },
                  [
                    h('header', [h('span', 'Settlement'), h(Icon, { name: 'check', size: 12 })]),
                    h('strong', { class: 'an-settlement-amount' }, '$1,284.60'),
                    h('span', { class: 'an-settlement-subtitle' }, 'Net to your account'),
                    h('div', { class: 'an-settlement-breakdown' }, [
                      h('div', [h('span', 'Payments'), h('span', '$1,320.00')]),
                      h('div', [h('span', 'Fees'), h('span', '−$35.40')]),
                    ]),
                  ],
                ),
                h(
                  'div',
                  {
                    class: 'an-arrival-note',
                    'data-target': 'arrival-note',
                    'data-visible': (s.phase >= 4 && !s.clearing) || undefined,
                    style: compact
                      ? { left: '32px', top: '536px', width: `${width - 64}px` }
                      : { left: '28px', top: '372px', width: '224px' },
                  },
                  [h('strong', 'Expected arrival'), h('span', 'Oct 27 · Checking •0814')],
                ),
                h(Connector, {
                  class: 'an-record-link an-fine-dotted',
                  from,
                  to,
                  route: compact ? 'straight' : 'v',
                  dots: 'end',
                  dashed: true,
                  show: measured && s.phase >= 1,
                }),
                h(Connector, {
                  class: 'an-detail-leader',
                  from: leaderFrom,
                  to: leaderTo,
                  route: 'straight',
                  dots: 'none',
                  show: measured && s.phase >= 3,
                }),
                h('span', {
                  class: 'an-composed-rest',
                  'data-target': 'payout-rest',
                  style: { left: `${width - 36}px`, top: `${compact ? 280 : 350}px` },
                }),
              ],
            )
          },
        },
      )
    }
  },
})

export default CollectionStudy
</script>
