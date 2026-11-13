<script lang="ts">
export const sceneLessons = [
  { id: 'dashboard-phone', title: 'Compose the two-device story', note: 'A payment arrives on the dashboard and phone. Give each device a readable role; keep the amount and confirmation visible together.', bad: 'The phone hides the payment it is explaining', good: 'Dashboard and phone share the story without covering it' },
  { id: 'window-satellite', title: 'Place a satellite around the story', note: 'An export window and its finished package. The receipt can overlap the window, but the settings and export action still need their own space.', bad: 'The receipt sits over the settings and action', good: 'The receipt straddles a quiet edge of the window' },
  { id: 'window-focus', title: 'Choose one window to lead', note: 'Assets, resolved feedback and a release ready to publish. Use depth to keep the supporting windows present while the final action leads.', bad: 'Three active windows compete for attention', good: 'Supporting windows recede behind the publish step' },
  { id: 'colored-layers', title: 'Use the ground to frame the layers', note: 'A paid invoice and its upcoming bank deposit. The background can carry warmth without painting every surface and status the same color.', bad: 'Ground, invoice and deposit compete in one saturated field', good: 'A warm ground frames distinct, readable layers' },
  { id: 'material-contrast', title: 'Separate dark and light materials', note: 'A dark file workspace with a light document preview. Each material needs its own foreground, edge and depth against the surrounding scene.', bad: 'Inherited colors flatten the dark and light surfaces', good: 'Each surface keeps readable ink and a distinct boundary' },
  { id: 'story-crop', title: 'Crop to the action and payoff', note: 'A library with a launch package ready to download. Keep the useful part at reading size; the rest of the application can continue beyond the frame.', bad: 'The whole application becomes a thumbnail', good: 'A deliberate crop keeps the package and action readable' },
  { id: 'result-weight', title: 'Give the result the most weight', note: 'A file has just uploaded into a folder. Ask what the eye lands on first: it should be the file the story is about, not the list around it.', bad: 'The new file is one thin row in a long list', good: 'Fewer, larger rows; the new file is the heaviest thing in the frame' },
  { id: 'crop-filler', title: 'Crop filler, never the story', note: 'The same folder, run off the right edge. A crop may cut placeholder columns; it must leave every value the story depends on whole.', bad: 'The crop cuts the size the story ends on', good: 'The crop falls past the last value that matters' },
  { id: 'tile-lead', title: 'Give one tile the lead', note: 'Four features in a grid. Equal tiles with equal content read as a template; one hero tile and quieter neighbors give the eye a place to start.', bad: 'Four equal tiles, each a heading and bars', good: 'One hero tile with the product; the others a number, a sentence, a mark' },
] as const

type SceneId = typeof sceneLessons[number]['id']
</script>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, type PropType } from 'vue'
import { Phone, Stage, Window } from '../kit'
import './scenes.css'

const props = defineProps<{
  lessonId: string
}>()

const lesson = computed(() => sceneLessons.find((item) => item.id === props.lessonId))

type MarkKind = 'check' | 'file' | 'arrow' | 'download'
const MARK_PATHS: Record<MarkKind, string> = {
  check: 'm4 10 4 4 8-8',
  file: 'M5 2h7l4 4v12H5zM12 2v4h4M8 10h5M8 13h5',
  arrow: 'M3 10h14m-5-5 5 5-5 5',
  download: 'M10 2v10m-4-4 4 4 4-4M4 14v4h12v-4',
}

const Mark = defineComponent({
  props: {
    kind: { type: String as PropType<MarkKind>, default: 'check' },
  },
  setup(p) {
    return () =>
      h('svg', { class: 'cs-mark', width: '18', height: '18', viewBox: '0 0 20 20', 'aria-hidden': 'true' }, [
        h('path', { d: MARK_PATHS[p.kind] }),
      ])
  },
})

const FOLDER = [96, 132, 104, 80, 120, 92, 112, 100, 126, 88, 116, 98, 108, 84] as const
const MINI_BARS = [26, 42, 36, 57, 72] as const
const EQUAL_TILES = ['Write together', 'Find anything', 'Works offline', 'Connects your tools'] as const

const FileList = defineComponent({
  props: {
    rows: { type: Number, required: true },
    big: { type: Boolean, required: true },
  },
  setup(p) {
    return () =>
      h('div', { class: 'cs-files-list', 'data-big': p.big || undefined }, [
        h('div', { class: 'cs-fl-head' }, [h('span', 'Name'), h('span', 'Modified'), h('span', 'Size')]),
        h('div', { class: 'cs-fl-row', 'data-new': '' }, [
          h('span', { class: 'cs-fl-name' }, [h(Mark, { kind: 'file' }), 'Launch deck.pdf']),
          h('span', 'Just now'),
          h('span', '4.2 MB'),
        ]),
        ...FOLDER.slice(0, p.rows).map((w, i) =>
          h('div', { class: 'cs-fl-row', key: i }, [
            h('span', { class: 'cs-fl-name' }, [
              h(Mark, { kind: 'file' }),
              h('i', { style: { width: `${p.big ? w : w * 0.8}px` } }),
            ]),
            h('span', [h('i', { style: { width: `${54 + (i % 3) * 8}px` } })]),
            h('span', [h('i', { style: { width: `${26 + (i % 4) * 5}px` } })]),
          ]),
        ),
      ])
  },
})

const frameRefs = ref<(HTMLDivElement | null)[]>([null, null])
const compactWidths = ref<[number, number]>([340, 340])
let observers: ResizeObserver[] = []

onMounted(() => {
  observers = [0, 1].map((idx) => {
    const el = frameRefs.value[idx]
    const measure = () => {
      const node = frameRefs.value[idx]
      if (!node) return
      compactWidths.value[idx] = Math.min(340, Math.max(280, Math.floor(node.getBoundingClientRect().width)))
    }
    measure()
    const obs = new ResizeObserver(measure)
    if (el) obs.observe(el)
    return obs
  })
})

onBeforeUnmount(() => {
  observers.forEach((o) => o.disconnect())
})
</script>

<template>
  <section v-if="lesson" class="cs-lesson">
    <header>
      <div>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.note }}</p>
      </div>
    </header>
    <div class="cs-pair">
      <figure v-for="(good, idx) in [false, true]" :key="String(good)" class="cs-figure">
        <div class="cs-side-label">{{ good ? 'Considered composition' : 'Composition problem' }}</div>
        <div
          :ref="(el: any) => (frameRefs[idx] = el)"
          class="cs-frame"
          :data-narrow="compactWidths[idx] < 320 || undefined"
          :style="{ '--cs-width': `${compactWidths[idx]}px` }"
        >
          <Stage
            :width="540"
            :height="420"
            :compact="{ below: 520, width: compactWidths[idx], height: 520 }"
            class="cs-stage"
            v-slot="{ layout }"
          >
            <!-- result-weight -->
            <div
              v-if="lesson.id === 'result-weight'"
              class="cs-scene cs-upload"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <Window title="Projects" lights="grey" class="cs-upload-window">
                <FileList :rows="good ? 8 : 14" :big="good" />
              </Window>
            </div>

            <!-- crop-filler -->
            <div
              v-else-if="lesson.id === 'crop-filler'"
              class="cs-scene cs-upload cs-cropcut"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <Window title="Projects" lights="grey" class="cs-upload-window">
                <FileList :rows="8" big />
              </Window>
            </div>

            <!-- tile-lead -->
            <div
              v-else-if="lesson.id === 'tile-lead'"
              class="cs-scene cs-tiles"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <template v-if="!good">
                <div v-for="t in EQUAL_TILES" :key="t" class="cs-tile">
                  <h3>{{ t }}</h3>
                  <div class="cs-tile-bars"><i /><i /><i /></div>
                </div>
              </template>
              <template v-else>
                <div class="cs-tile cs-tile-hero">
                  <h3>Write together</h3>
                  <Window title="Q3 plan" lights="grey" class="cs-tile-window">
                    <div class="cs-tile-doc">
                      <strong>Beta opens to every team on May 14.</strong>
                      <span class="cs-tile-caret">Priya</span>
                      <div class="cs-tile-bars"><i /><i /></div>
                    </div>
                  </Window>
                </div>
                <div class="cs-tile">
                  <h3>Find anything</h3>
                  <div class="cs-tile-big">0.2s</div>
                </div>
                <div class="cs-tile">
                  <h3>Works offline</h3>
                  <p>Edits on the plane merge when you land.</p>
                </div>
                <div class="cs-tile">
                  <h3>Connects your tools</h3>
                  <div class="cs-tile-marks"><i /><i /><i /></div>
                </div>
              </template>
            </div>

            <!-- dashboard-phone -->
            <div
              v-else-if="lesson.id === 'dashboard-phone'"
              class="cs-scene cs-device"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <Window title="Payments" lights="grey" class="cs-device-window">
                <div class="cs-dashboard">
                  <div class="cs-eyebrow">This month</div>
                  <h3>$12,480<span>received</span></h3>
                  <div class="cs-mini-chart" aria-label="Payments grew over the last five days">
                    <i v-for="(v, i) in MINI_BARS" :key="i" :style="{ height: `${v}px` }" />
                  </div>
                  <div class="cs-payment-row">
                    <div>Fable Studio<small>Invoice 1042</small></div>
                    <strong>$2,400</strong>
                  </div>
                  <span class="cs-status"><Mark />Payment received</span>
                </div>
              </Window>
              <Phone :width="228" frame="silver" class="cs-device-phone">
                <div class="cs-phone-app">
                  <h3>Payments</h3>
                  <p>Today</p>
                  <div class="cs-phone-payment">
                    <span class="cs-phone-check"><Mark /></span>
                    <h4>Payment received</h4>
                    <strong>$2,400</strong>
                    <p>Fable Studio · Invoice 1042</p>
                  </div>
                  <div class="cs-phone-link">View payment <Mark kind="arrow" /></div>
                </div>
              </Phone>
            </div>

            <!-- window-satellite -->
            <div
              v-else-if="lesson.id === 'window-satellite'"
              class="cs-scene cs-export"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <Window title="Asset export" lights="grey" class="cs-export-window">
                <div class="cs-export-content">
                  <div>
                    <h3>Campaign assets</h3>
                    <p>24 assets selected</p>
                  </div>
                  <div class="cs-export-settings">
                    <span>Format<strong>PNG</strong></span>
                    <span>Resolution<strong>2× original</strong></span>
                  </div>
                  <span class="cs-action">Export package<Mark kind="arrow" /></span>
                </div>
                <div class="cs-export-preview" aria-hidden="true"><i /><i /><i /></div>
              </Window>
              <div class="cs-export-receipt">
                <span class="cs-receipt-icon"><Mark kind="download" /></span>
                <div>
                  <h3>Package ready</h3>
                  <p>Campaign-assets.zip</p>
                  <span>24 files · 18.6 MB</span>
                </div>
                <span class="cs-status"><Mark />Saved to downloads</span>
              </div>
            </div>

            <!-- window-focus -->
            <div
              v-else-if="lesson.id === 'window-focus'"
              class="cs-scene cs-focus"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <Window title="Assets" lights="grey" class="cs-focus-assets">
                <div class="cs-back-content">
                  <span class="cs-status"><Mark />24 assets ready</span>
                  <div class="cs-file-tiles" aria-hidden="true"><i /><i /><i /></div>
                </div>
              </Window>
              <Window title="Feedback" lights="grey" class="cs-focus-feedback">
                <div class="cs-back-content">
                  <span class="cs-status"><Mark />All comments resolved</span>
                  <p>Reviewed by Maya and Jon</p>
                </div>
              </Window>
              <Window title="Publish" lights="grey" class="cs-focus-publish">
                <div class="cs-publish-content">
                  <h3>Ready to launch</h3>
                  <p>Homepage · Summer release</p>
                  <div class="cs-publish-checks">
                    <span class="cs-status"><Mark />Assets approved</span>
                    <span class="cs-status"><Mark />Feedback resolved</span>
                  </div>
                  <span class="cs-action">Publish release<Mark kind="arrow" /></span>
                </div>
              </Window>
            </div>

            <!-- colored-layers -->
            <div
              v-else-if="lesson.id === 'colored-layers'"
              class="cs-scene cs-color"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <div class="cs-invoice">
                <div class="cs-invoice-head">
                  <span>Invoice 1042</span>
                  <span class="cs-status"><Mark />Paid</span>
                </div>
                <h3>Studio Lake</h3>
                <p>Design retainer · June</p>
                <div class="cs-invoice-total">$840.00</div>
                <div class="cs-invoice-detail"><span>Design services</span><span>$800.00</span></div>
                <div class="cs-invoice-detail"><span>Tax</span><span>$40.00</span></div>
                <div class="cs-invoice-paid"><Mark />Paid June 12</div>
              </div>
              <div class="cs-deposit">
                <span class="cs-eyebrow">Bank deposit</span>
                <h3>$840.00</h3>
                <p>Arriving tomorrow</p>
                <div><span>Checking ··2048</span><Mark kind="arrow" /></div>
              </div>
            </div>

            <!-- material-contrast -->
            <div
              v-else-if="lesson.id === 'material-contrast'"
              class="cs-scene cs-material"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <Window title="Workspace files" lights="grey" class="cs-files-window">
                <div class="cs-files-content">
                  <h3>Launch assets</h3>
                  <p>Shared with the product team</p>
                  <div class="cs-file-row" data-selected>
                    <Mark kind="file" />
                    <div>Launch brief<small>Updated today</small></div>
                    <span>PDF</span>
                  </div>
                  <div class="cs-file-row">
                    <Mark kind="file" />
                    <div>Brand guidelines<small>Updated yesterday</small></div>
                    <span>PDF</span>
                  </div>
                </div>
              </Window>
              <div class="cs-document-preview">
                <div class="cs-preview-meta"><span>Document preview</span><span>1 / 4</span></div>
                <h3>Launch brief</h3>
                <p>A simpler way to work together.</p>
                <div class="cs-doc-rule" />
                <h4>The release</h4>
                <p>Shared projects, clear ownership, and one place for feedback.</p>
                <div class="cs-preview-foot"><span>Ready for review</span><Mark kind="arrow" /></div>
              </div>
            </div>

            <!-- story-crop -->
            <div
              v-else
              class="cs-scene cs-crop"
              :data-good="good || undefined"
              :data-compact="layout === 'compact' || undefined"
            >
              <Window title="Asset library" lights="grey" class="cs-library-window">
                <template #toolbar><span /></template>
                <div class="cs-library-shell">
                  <aside>
                    <strong>Workspace</strong>
                    <span>Overview</span>
                    <span data-active>Assets</span>
                    <span>Activity</span>
                    <span>Settings</span>
                  </aside>
                  <div class="cs-library-main">
                    <div class="cs-eyebrow">Campaign launch</div>
                    <h3>Launch package</h3>
                    <p>Everything your team needs to publish.</p>
                    <div class="cs-bundle">
                      <span class="cs-bundle-icon"><Mark kind="file" /></span>
                      <div>
                        <strong>Summer release</strong>
                        <span>24 assets · 18.6 MB</span>
                      </div>
                    </div>
                    <span class="cs-status"><Mark />All 24 assets ready</span>
                    <span class="cs-action">Download package<Mark kind="arrow" /></span>
                  </div>
                  <div class="cs-library-context" aria-hidden="true"><i /><i /><i /><i /><i /><i /></div>
                </div>
              </Window>
            </div>
          </Stage>
        </div>
        <figcaption>{{ good ? lesson.good : lesson.bad }}</figcaption>
      </figure>
    </div>
  </section>
</template>
