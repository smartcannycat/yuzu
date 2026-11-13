<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId, type CSSProperties } from 'vue'
import { Connector, Follow, Icon, Stage, States, type Act, type Rect } from '../../kit'
import './annotations.css'
import { CollectionStudy, DetailStudy } from './composed'

const lakePhoto = new URL('../wikipedia/kawaguchiko.jpg', import.meta.url).href

const studies = [
  { id: 'collect', title: 'Usage into an invoice', note: 'Connect three usage sources to one invoice. Blue dots keep flowing after its first update; a matching shared delivery shows where those inputs meet.' },
  { id: 'detail', title: 'A payout and its detail', note: 'Select one payout. A dotted link opens its settlement; a quieter solid leader explains arrival without replacing the product view.' },
  { id: 'chart', title: 'A chart point', note: 'Select one result. The leader joins the measured point to its explanation, then leaves when the selection clears.' },
  { id: 'measure', title: 'Selection guides', note: 'Resize a card by its handle. Its guides and dimensions belong to the same box, including on the return drag.' },
  { id: 'flow', title: 'A request and its reply', note: 'Send a billing event. The solid request points out; the dashed acknowledgement returns only after the receipt arrives.' },
  { id: 'branch', title: 'A shared processing graph', note: 'Store one asset, then send it along a shared trunk to three jobs. Each branch meets its destination cleanly; Clear jobs dismisses the result.' },
  { id: 'stream', title: 'An ongoing event stream', note: 'Connect the feed once. A quiet route stays fixed while moving dashes show events arriving in the activity table; reduced motion keeps its direction visible.' },
  { id: 'follow', title: 'Following a layer', note: 'Arrange a selected layer. Its annotation travels and resizes with the object, then fades intact when selection clears.' },
] as const
type Study = typeof studies[number]['id']

const initialStudy = (): Study => {
  const value = typeof window === 'undefined' ? null : new URL(window.location.href).searchParams.get('annotation')
  return studies.find(study => study.id === value)?.id ?? 'collect'
}
const point = (r: Rect) => ({ x: r.x + r.width / 2, y: r.y + r.height / 2 })

type ChartState = { selected: boolean }
async function chartScript(a: Act<ChartState>) {
  a.mark('start'); await a.wait(650)
  await a.move('point'); await a.click(); a.mark('callout')
  await a.set({ selected: true }); await a.move('chart-rest', { duration: 360 }); await a.wait(2440)
  await a.click(); a.mark('clear')
  await a.set({ selected: false }); await a.wait(700); a.mark('done')
  await a.wait(700)
}

type MeasureState = { selected: boolean; width: number; height: number }

type FlowState = { step: number }
async function flowScript(a: Act<FlowState>) {
  a.mark('start'); await a.wait(650); await a.move({ at: 'send', x: 0.92, y: 0.85 }); await a.click()
  a.mark('request'); await a.set({ step: 1 })
  await a.move('flow-rest', { duration: 350 }); await a.wait(1050)
  a.mark('reply'); await a.set({ step: 2 }); await a.wait(1100)
  a.mark('acknowledged'); await a.set({ step: 3 }); await a.wait(2200)
  await a.move('clear-trace'); await a.click(); a.mark('clear')
  await a.set({ step: 0 }); await a.wait(750); a.mark('done'); await a.wait(650)
}

type FollowState = { selected: boolean; arranged: boolean }
async function followScript(a: Act<FollowState>) {
  a.mark('start'); await a.wait(650); await a.move('layer'); await a.click()
  await a.set({ selected: true }); await a.wait(1000)
  await a.move('arrange'); await a.click(); a.mark('arrange')
  await a.set({ arranged: true }); await a.wait(2600)
  await a.move('restore'); await a.click(); a.mark('restore')
  await a.set({ arranged: false }); await a.wait(1400)
  await a.move('follow-rest'); await a.click(); a.mark('clear')
  await a.set({ selected: false }); await a.wait(650); a.mark('done'); await a.wait(650)
}

type BranchState = { phase: number; clearing: boolean }
async function branchScript(a: Act<BranchState>) {
  a.mark('start'); await a.wait(650); await a.move({ at: 'process-asset', x: 0.92, y: 0.85 }); await a.click()
  a.mark('upload'); await a.set({ phase: 1 })
  await a.move('graph-rest', { duration: 350 }); await a.wait(750)
  a.mark('spine'); await a.set({ phase: 2 }); await a.wait(1100)
  a.mark('branches'); await a.set({ phase: 3 }); await a.wait(1100)
  a.mark('ready'); await a.set({ phase: 4 }); await a.wait(2300)
  await a.move('clear-jobs'); await a.click(); a.mark('clear')
  await a.set({ clearing: true }); await a.wait(350)
  await a.set({ phase: 0, clearing: false }); await a.wait(700); a.mark('done'); await a.wait(650)
}
const branchNames = ['Preview', 'Search', 'Archive']

const STREAM_REVEAL_MS = 700
type StreamState = { connected: boolean; receiving: boolean }
async function streamScript(a: Act<StreamState>) {
  a.mark('start'); await a.wait(800); await a.move({ at: 'connect-stream', x: 0.92, y: 0.85 }); await a.click()
  a.mark('connected'); await a.set({ connected: true })
  await a.move('stream-rest', { duration: 350 }); await a.wait(STREAM_REVEAL_MS + 100 - 350)
  a.mark('live'); await a.set({ receiving: true }); await a.wait(800)
  await a.wait(2250)
  // The connection stays open. Only the line's phase continues; there is no
  // polling script or invisible reset of the successful connection.
  await a.wait(800); a.mark('done')
}

const selected = ref<Study>(initialStudy())
const revision = ref(0)
const width = ref<number | null>(null)
const host = ref<HTMLDivElement | null>(null)
const id = useId()
const streamRevealId = `an-stream-${useId().replace(/:/g, '')}`

const selectStudy = (value: Study) => {
  selected.value = value
  const url = new URL(location.href)
  url.searchParams.set('annotation', value)
  history.replaceState(null, '', url)
  if (parent !== window) parent.postMessage({ type: 'stageshow:status', annotation: value }, location.origin)
}

let observer: ResizeObserver | null = null
onMounted(() => {
  const node = host.value
  if (!node) return
  const read = () => {
    width.value = Math.min(600, Math.floor(node.getBoundingClientRect().width))
  }
  read()
  observer = new ResizeObserver(read)
  observer.observe(node)
})
onBeforeUnmount(() => {
  observer?.disconnect()
})

const active = computed(() => studies.find(study => study.id === selected.value)!)

const measureConfig = computed(() => {
  const w = width.value ?? 600
  const compact = w < 480
  const start = { width: compact ? 168 : 256, height: compact ? 136 : 150 }
  const finish = { width: compact ? 188 : 304, height: compact ? 160 : 180 }
  const x = compact
    ? w < 330
      ? 36 + (w - 288) / 2
      : Math.max(36, Math.round((w - finish.width - 48) / 2))
    : (w - finish.width) / 2 - 14
  const script = async (a: Act<MeasureState>) => {
    a.mark('start'); await a.wait(650); await a.move('measure-card'); await a.click()
    await a.set({ selected: true }); await a.wait(500)
    await a.move('resize'); const from = a.center('resize'); a.mark('resize')
    await a.drag(
      { x: from.x + finish.width - start.width, y: from.y + finish.height - start.height },
      (p, origin) => a.put({ width: start.width + p.x - origin.x, height: start.height + p.y - origin.y }),
      { duration: 1400 },
    )
    await a.set(finish); await a.wait(2100)
    await a.move('resize'); const back = a.center('resize'); a.mark('restore')
    await a.drag(
      { x: back.x - finish.width + start.width, y: back.y - finish.height + start.height },
      (p, origin) => a.put({ width: finish.width + p.x - origin.x, height: finish.height + p.y - origin.y }),
      { duration: 1400 },
    )
    await a.set(start); await a.move('measure-rest'); await a.click()
    await a.set({ selected: false }); await a.wait(650); a.mark('done'); await a.wait(650)
  }
  return { compact, start, finish, x, script }
})

function flowPoints(w: number, rect: (name: string) => Rect) {
  const compact = w < 480
  const a = rect('billing'), b = rect('workspace')
  const from = compact ? { x: a.x + a.width / 2 - 28, y: a.y + a.height } : { x: a.x + a.width, y: a.y + a.height / 2 - 18 }
  const to = compact ? { x: b.x + b.width / 2 - 28, y: b.y } : { x: b.x, y: b.y + b.height / 2 - 18 }
  const backFrom = compact ? { x: to.x + 56, y: to.y } : { x: to.x, y: to.y + 40 }
  const backTo = compact ? { x: from.x + 56, y: from.y } : { x: from.x, y: from.y + 40 }
  return { compact, a, b, from, to, backFrom, backTo }
}

function branchGeo(w: number, s: BranchState, rect: (name: string) => Rect) {
  const compact = w < 520
  const source = rect('asset-source')
  const outputs = branchNames.map((_, i) => rect(`asset-output-${i}`))
  const ports = outputs.map(r => compact ? { x: r.x + r.width / 2, y: r.y } : { x: r.x, y: r.y + r.height / 2 })
  const start = compact ? { x: source.x + source.width / 2, y: source.y + source.height } : { x: source.x + source.width, y: source.y + source.height / 2 }
  const junction = compact ? { x: start.x, y: 216 } : { x: w - 278, y: ports[1].y }
  const ends = compact ? ports.map(p => ({ x: p.x, y: junction.y })) : ports.map(p => ({ x: junction.x, y: p.y }))
  const measured = source.width > 0 && outputs.every(r => r.width > 0) && !s.clearing
  return { compact, ports, start, junction, ends, measured }
}

function streamGeo(w: number, rect: (name: string) => Rect) {
  const compact = w < 520
  const a = rect('stream-source'), b = rect('stream-destination')
  const from = compact ? { x: a.x + a.width / 2, y: a.y + a.height } : { x: a.x + a.width, y: a.y + a.height / 2 }
  const to = compact ? { x: b.x + b.width / 2, y: b.y } : { x: b.x, y: from.y }
  const path = `M${from.x} ${from.y}L${to.x} ${to.y}`
  const arrow = compact ? `M${to.x - 3.5} ${to.y - 5}L${to.x} ${to.y}L${to.x + 3.5} ${to.y - 5}` : `M${to.x - 5} ${to.y - 3.5}L${to.x} ${to.y}L${to.x - 5} ${to.y + 3.5}`
  return { compact, a, b, from, to, path, arrow }
}

function followBounds(w: number) {
  const compact = w < 480
  const start = { x: compact ? 36 : 90, y: compact ? 181 : 164, width: compact ? 168 : 188, height: 110 }
  const end = { x: compact ? w - 228 : w - 302, y: compact ? 224 : 176, width: compact ? 192 : 242, height: compact ? 128 : 142 }
  return { compact, start, end }
}
</script>

<template>
  <div ref="host" class="an-gallery">
    <div class="an-picker">
      <label :for="id">Study</label>
      <select :id="id" :value="selected" @change="event => selectStudy((event.target as HTMLSelectElement).value as Study)">
        <option v-for="study in studies" :key="study.id" :value="study.id">{{ study.title }}</option>
      </select>
      <button type="button" aria-label="Replay annotation study" @click="revision++">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M3.2 4.3A4.5 4.5 0 1 1 2.6 8M3.2 1.8v2.8H6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    </div>

    <div :key="`${selected}-${revision}`" class="an-scene" :data-annotation="selected">
      <template v-if="width !== null">
        <CollectionStudy v-if="selected === 'collect'" :width="width" />
        <DetailStudy v-else-if="selected === 'detail'" :width="width" />

        <!-- ChartStudy -->
        <Stage
          v-else-if="selected === 'chart'"
          :width="width"
          :height="width < 480 ? 420 : 380"
          :initial="{ selected: false }"
          :poster="{ selected: true }"
          :script="chartScript"
          :cursor="{ at: { x: 25, y: 340 } }"
          greys="cool"
          accent="#5375c8"
          :class="`an-study an-chart${width < 480 ? ' an-chart--compact' : ''}`"
          v-slot="{ state: s, rect }"
        >
          <section class="an-chart-panel" aria-label="API usage chart">
            <header class="an-product-head">
              <strong>API requests</strong>
              <span>Last 7 days <Icon name="chevron-down" :size="11" /></span>
            </header>
            <div class="an-chart-total">8,642 <span>this week</span></div>
            <div class="an-chart-note" data-target="chart-note" :data-visible="s.selected || undefined">
              <strong>Release v2</strong><span>1,840 requests</span>
            </div>
            <div class="an-plot">
              <svg viewBox="0 0 400 140" preserveAspectRatio="none" aria-hidden="true">
                <path class="an-chart-grid" d="M0 25H400M0 70H400M0 115H400" />
                <path class="an-chart-area" d="M0 112L44 104L87 108L130 80L174 88L217 60L260 30L304 56L348 46L400 20V140H0Z" />
                <path class="an-chart-line" d="M0 112L44 104L87 108L130 80L174 88L217 60L260 30L304 56L348 46L400 20" />
              </svg>
              <span class="an-chart-point" data-target="point" data-cursor="hand" :data-selected="s.selected || undefined" />
            </div>
            <div class="an-chart-axis"><span>Mon</span><span>Wed</span><span>Fri</span><span>Sun</span></div>
            <span class="an-chart-rest" data-target="chart-rest" />
          </section>
          <!-- Meet the bottom edge vertically. A vertical-first elbow would
               finish horizontally along the note's border. -->
          <Connector
            class="an-chart-leader"
            :from="point(rect('point'))"
            :to="{ x: rect('chart-note').x + rect('chart-note').width / 2, y: rect('chart-note').y + rect('chart-note').height }"
            route="h"
            dots="none"
            :show="s.selected && rect('point').width > 0 && rect('chart-note').width > 0"
          />
        </Stage>

        <!-- MeasureStudy -->
        <Stage
          v-else-if="selected === 'measure'"
          :key="measureConfig.compact ? 'compact' : 'wide'"
          :width="width"
          :height="measureConfig.compact ? 420 : 380"
          :initial="{ selected: false, ...measureConfig.start }"
          :poster="{ selected: true, ...measureConfig.finish }"
          :script="measureConfig.script"
          :cursor="{ at: { x: width - 30, y: 340 } }"
          greys="cool"
          accent="#6979c9"
          :class="`an-study an-measure${width < 330 ? ' an-measure--narrow' : ''}`"
          v-slot="{ state: s }"
        >
          <div class="an-canvas-panel">
            <header class="an-product-head"><strong>Board layout</strong><span>Project card</span></header>
            <span class="an-canvas-rest" data-target="measure-rest" />
          </div>
          <div
            class="an-selection"
            :data-selected="s.selected || undefined"
            :style="{
              left: `${measureConfig.x}px`,
              top: `${measureConfig.compact ? 137 : 112}px`,
              width: `${s.width}px`,
              height: `${s.height}px`,
            }"
          >
            <div class="an-design-card" data-target="measure-card" data-cursor="hand">
              <div><span class="an-card-project">Website refresh</span><strong>Release checklist</strong></div>
              <div class="an-card-completion"><strong>6<span> / 8</span></strong><span>tasks complete</span></div>
              <div class="an-card-bottom">
                <div class="an-card-progress"><i /></div>
                <footer><span>Design team</span><time>Oct 28</time></footer>
              </div>
            </div>
            <div class="an-selection-ring" />
            <span class="an-resize-handle" data-target="resize" data-cursor="crosshair" />
            <div class="an-width-guide"><span>{{ Math.round(s.width) }} px</span></div>
            <div class="an-height-guide"><span>{{ Math.round(s.height) }}</span></div>
            <span class="an-layer-label">Project</span>
          </div>
        </Stage>

        <!-- FlowStudy -->
        <Stage
          v-else-if="selected === 'flow'"
          :width="width"
          :height="width < 480 ? 496 : 330"
          :initial="{ step: 0 }"
          :poster="{ step: 3 }"
          :script="flowScript"
          :cursor="{ at: { x: 25, y: width < 480 ? 360 : 270 } }"
          greys="cool"
          accent="#468575"
          :class="`an-study an-flow${width < 480 ? ' an-flow--compact' : ''}`"
          v-slot="{ state: s, rect }"
        >
          <header class="an-flow-title">
            <strong>Webhook delivery</strong>
            <span data-target="clear-trace" data-cursor="hand">Clear trace</span>
          </header>
          <section
            class="an-flow-node an-flow-source"
            data-target="billing"
            :style="width < 480 ? { left: '32px', top: '68px', width: `${width - 64}px` } : { left: '32px', top: '90px', width: '220px' }"
          >
            <div class="an-node-name"><strong>Invoice paid</strong><span class="an-event-kind">Event</span></div>
            <code>invoice.paid</code>
            <div class="an-event-record"><span>Invoice <b>0084</b></span><strong>$189.00</strong></div>
            <footer class="an-event-footer">
              <span>Today, 14:32</span>
              <div class="an-send" data-target="send" data-cursor="hand">
                <States :value="String(s.step)" :states="{ 0: 'Send event', 1: 'Sending…', 2: 'Awaiting reply', 3: 'Delivered' }" />
              </div>
            </footer>
          </section>
          <section
            class="an-flow-node an-flow-destination"
            data-target="workspace"
            :data-received="s.step >= 2 || undefined"
            :style="width < 480 ? { left: '32px', top: '330px', width: `${width - 64}px` } : { left: `${width - 196}px`, top: '115px', width: '164px' }"
          >
            <div class="an-node-name"><Icon name="bell" :size="13" /><strong>Activity</strong></div>
            <span class="an-endpoint">Billing notifications</span>
            <div class="an-receipt">
              <States align="start" :value="s.step >= 2 ? 'received' : 'waiting'" :states="{ waiting: 'Waiting for event', received: 'Payment received' }" />
            </div>
            <div class="an-receipt-amount" :data-visible="s.step >= 2 || undefined">$189.00 <span>Invoice 0084</span></div>
          </section>
          <Connector
            class="an-request"
            :from="flowPoints(width, rect).from"
            :to="flowPoints(width, rect).to"
            route="straight"
            :show="s.step >= 1 && flowPoints(width, rect).a.width > 0"
            arrow
            label="POST"
            :label-at="width < 480 ? 0.37 : 0.5"
          />
          <Connector
            class="an-response"
            :from="flowPoints(width, rect).backFrom"
            :to="flowPoints(width, rect).backTo"
            route="straight"
            :show="s.step >= 2 && flowPoints(width, rect).b.width > 0"
            arrow
            dashed
            label="200 OK"
            :label-at="width < 480 ? 0.37 : 0.5"
          />
          <span class="an-composed-rest" data-target="flow-rest" :style="{ left: `${width - 34}px`, top: `${width < 480 ? 275 : 290}px` }" />
        </Stage>

        <!-- BranchStudy -->
        <Stage
          v-else-if="selected === 'branch'"
          :width="width"
          :height="width < 520 ? 340 : 320"
          :initial="{ phase: 0, clearing: false }"
          :poster="{ phase: 4, clearing: false }"
          :script="branchScript"
          :cursor="{ at: { x: 25, y: width < 520 ? 312 : 292 } }"
          greys="cool"
          accent="#8659cc"
          class="an-study an-branch"
          v-slot="{ state: s, rect }"
        >
          <header class="an-flow-title">
            <strong>Asset processing</strong>
            <span data-target="clear-jobs" data-cursor="hand">Clear jobs</span>
          </header>
          <section
            class="an-asset-source"
            data-target="asset-source"
            :style="width < 520 ? { left: `${(width - 180) / 2}px`, top: '76px', width: '180px', height: '100px' } : { left: '34px', top: '110px', width: '180px', height: '100px' }"
          >
            <div class="an-asset-file">
              <Icon name="file" :size="22" class="an-file-preview" />
              <div><strong>cover.jpg</strong><span>2.4 MB · Image</span></div>
            </div>
            <div class="an-asset-action" data-target="process-asset" data-cursor="hand">
              <States :value="s.phase === 0 ? 'idle' : s.phase === 1 ? 'storing' : 'stored'" :states="{ idle: 'Process file', storing: 'Storing…', stored: 'Stored' }" />
            </div>
          </section>
          <section
            v-for="(name, i) in branchNames"
            :key="name"
            class="an-asset-output"
            :data-compact="(width < 520) || undefined"
            :data-ready="s.phase >= (i === 1 ? 3 : 4) || undefined"
            :aria-label="`${name}: ${s.phase >= (i === 1 ? 3 : 4) ? 'ready' : 'waiting'}`"
            :style="width < 520 ? { left: `${16 + i * (width - 104) / 2}px`, top: '254px', width: '72px', height: '48px' } : { left: `${width - 214}px`, top: `${64 + i * 80}px`, width: '180px', height: '48px' }"
          >
            <strong class="an-job-pill" :data-target="`asset-output-${i}`">
              <span>{{ name }}</span>
              <span class="an-job-mark"><Icon name="check" :size="12" class="an-job-check" /></span>
            </strong>
          </section>
          <!-- Travel reaches the center first. Two non-overlapping spine halves
               grow out from there; outer branches wait for those arrivals.
               Connector owns each endpoint marker's actual arrival timing. -->
          <Connector
            class="an-asset-trunk"
            :from="branchGeo(width, s, rect).start"
            :to="branchGeo(width, s, rect).junction"
            route="straight"
            :show="branchGeo(width, s, rect).measured && s.phase >= 1"
          />
          <Connector
            v-for="i in [0, 2]"
            :key="`spine-${i}`"
            :class="`an-asset-spine an-asset-spine--${i}`"
            :from="branchGeo(width, s, rect).junction"
            :to="branchGeo(width, s, rect).ends[i]"
            route="straight"
            :show="branchGeo(width, s, rect).measured && s.phase >= 2"
          />
          <Connector
            v-for="(port, i) in branchGeo(width, s, rect).ports"
            :key="`branch-${i}`"
            :class="`an-asset-branch an-asset-branch--${i}`"
            :from="branchGeo(width, s, rect).ends[i]"
            :to="port"
            route="straight"
            arrow
            :show="branchGeo(width, s, rect).measured && s.phase >= (i === 1 ? 2 : 3)"
          />
          <span class="an-composed-rest" data-target="graph-rest" :style="{ left: '24px', top: `${width < 520 ? 188 : 256}px` }" />
        </Stage>

        <!-- StreamStudy -->
        <Stage
          v-else-if="selected === 'stream'"
          :width="width"
          :height="width < 520 ? 504 : 330"
          :initial="{ connected: false, receiving: false }"
          :poster="{ connected: true, receiving: true }"
          :script="streamScript"
          play="once"
          :cursor="{ at: { x: 25, y: width < 520 ? 356 : 270 } }"
          greys="cool"
          accent="#0d9488"
          :class="`an-study an-stream${width < 520 ? ' an-stream--compact' : ''}`"
          v-slot="{ state: s, rect }"
        >
          <header class="an-flow-title">
            <strong>Event stream</strong>
            <span class="an-stream-status" :data-live="s.receiving || undefined">
              <i /><States align="start" :value="s.receiving ? 'live' : s.connected ? 'opening' : 'idle'" :states="{ idle: 'Offline', opening: 'Connecting', live: 'Live' }" />
            </span>
          </header>
          <section
            class="an-stream-node an-stream-source"
            data-target="stream-source"
            :style="width < 520 ? { left: '32px', top: '68px', width: `${width - 64}px` } : { left: '32px', top: '123px', width: '160px' }"
          >
            <div class="an-stream-source-title">
              <span class="an-stream-source-icon"><Icon name="bolt" :size="16" /></span>
              <div><strong>Checkout</strong><span>Production</span></div>
            </div>
            <div class="an-stream-connect" data-target="connect-stream" data-cursor="hand">
              <States :value="s.receiving ? 'live' : s.connected ? 'opening' : 'idle'" :states="{ idle: 'Connect stream', opening: 'Connecting…', live: 'Connected' }" />
            </div>
          </section>
          <section
            class="an-stream-warehouse"
            data-target="stream-destination"
            :style="width < 520 ? { left: '32px', top: '266px', width: `${width - 64}px` } : { left: `${width - 276}px`, top: '80px', width: '244px' }"
          >
            <header><strong>Events</strong><span>Live feed</span></header>
            <div class="an-stream-columns"><span>Event</span><span>Time</span></div>
            <div class="an-stream-record" :data-visible="s.receiving || undefined">
              <span><i /><States align="start" :value="s.receiving ? 'live' : 'idle'" :states="{ idle: 'Checkout started', live: 'Checkout completed' }" /></span>
              <time><States align="end" :value="s.receiving ? 'live' : 'idle'" :states="{ idle: '14:31', live: '14:32' }" /></time>
            </div>
            <div class="an-stream-history"><span>Customer created</span><time>14:31</time></div>
            <div class="an-stream-history"><span>Session started</span><time>14:31</time></div>
            <footer class="an-stream-receiving" :data-live="s.receiving || undefined">
              <i /><States align="start" :value="s.receiving ? 'live' : s.connected ? 'opening' : 'idle'" :states="{ idle: 'Stream disconnected', opening: 'Opening route', live: 'Receiving events' }" />
            </footer>
          </section>
          <svg
            class="an-stream-route"
            :data-active="s.connected || undefined"
            :data-arrived="s.receiving || undefined"
            :data-ready="(streamGeo(width, rect).a.width > 0 && streamGeo(width, rect).b.width > 0) || undefined"
            :style="{ '--an-stream-reveal-duration': `${STREAM_REVEAL_MS}ms` } as CSSProperties"
            aria-hidden="true"
          >
            <defs>
              <mask :id="streamRevealId" maskUnits="userSpaceOnUse">
                <path class="an-stream-reveal" :d="streamGeo(width, rect).path" pathLength="1" />
              </mask>
            </defs>
            <path class="an-stream-underlay" :d="streamGeo(width, rect).path" />
            <path class="an-stream-phase" :d="streamGeo(width, rect).path" :mask="`url(#${streamRevealId})`" />
            <path class="an-stream-arrow" :d="streamGeo(width, rect).arrow" />
          </svg>
          <span
            class="an-stream-rate"
            :data-visible="s.receiving || undefined"
            :style="width < 520 ? { left: `${streamGeo(width, rect).from.x + 12}px`, top: `${(streamGeo(width, rect).from.y + streamGeo(width, rect).to.y) / 2 - 8}px` } : { left: `${(streamGeo(width, rect).from.x + streamGeo(width, rect).to.x) / 2}px`, top: `${streamGeo(width, rect).from.y - 26}px`, transform: 'translateX(-50%)' }"
          >
            1.2k / sec
          </span>
          <span class="an-stream-rest" data-target="stream-rest" :style="{ left: `${width - 34}px`, top: `${width < 520 ? 215 : 290}px` }" />
        </Stage>

        <!-- FollowStudy -->
        <Stage
          v-else
          :width="width"
          :height="width < 480 ? 420 : 380"
          :initial="{ selected: false, arranged: false }"
          :poster="{ selected: true, arranged: true }"
          :script="followScript"
          :cursor="{ at: { x: width - 25, y: 362 } }"
          greys="cool"
          accent="#6c7bb7"
          class="an-study an-follow"
          v-slot="{ state: s }"
        >
          <div class="an-canvas-panel">
            <header class="an-product-head">
              <strong>Travel board</strong>
              <div class="an-canvas-actions">
                <span data-target="arrange" data-cursor="hand">Arrange</span>
                <span data-target="restore" data-cursor="hand">Reset</span>
              </div>
            </header>
            <span class="an-canvas-rest" data-target="follow-rest" />
          </div>
          <!-- Object, leader and note share Follow's changing coordinate space.
               Reading the destination rect for an independent line would detach it
               while Follow is still traveling toward that destination. -->
          <Follow :to="s.arranged ? followBounds(width).end : followBounds(width).start" :stiffness="0.16" class="an-moving-layer">
            <div class="an-layer-art" data-target="layer" data-cursor="hand">
              <img :src="lakePhoto" alt="Mount Fuji reflected in Lake Kawaguchi" :draggable="false" />
            </div>
            <div class="an-follow-outline" :data-visible="s.selected || undefined" />
            <div class="an-attached-note" :data-visible="s.selected || undefined">
              <strong>Lake Kawaguchi</strong><span>Keep the reflection visible</span>
            </div>
            <svg class="an-attached-leader" :data-visible="s.selected || undefined" aria-hidden="true">
              <path d="M.75 0V18" /><circle cx=".75" cy="18" r="2" />
            </svg>
          </Follow>
        </Stage>
      </template>
    </div>

    <p class="an-description">{{ active.note }}</p>
  </div>
</template>
