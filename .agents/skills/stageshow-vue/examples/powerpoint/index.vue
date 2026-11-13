<script setup lang="ts">
import { defineComponent, h, useId, type CSSProperties, type PropType } from 'vue'
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  ClipboardPaste,
  Italic,
  LayoutDashboard,
  Layers,
  List,
  ListOrdered,
  Shapes,
  SquarePlus,
  Strikethrough,
  Underline,
  X,
} from 'lucide-vue-next'
import { Bar, Stage, Text, Window, type Act, type Layout } from '../../kit'
import './pp.css'

// PowerPoint for Mac: pick slide 2 in the rail, it opens in the editor, open
// Designer and pick a suggested layout, and the slide restyles in place (the
// rail thumbnail follows). Cmd+Z undoes it, the pane closes, slide 1 is
// picked again, so the loop ends where it began.

type Design = 'plain' | 'split' | 'band' | 'overlay'
type S = { slide: 1 | 2; pane: boolean; design: Design; picked: number; ideas: boolean }

const initial: S = { slide: 1, pane: false, design: 'plain', picked: 0, ideas: false }
const poster: S = { slide: 2, pane: true, design: 'split', picked: 2, ideas: true }

// Geometry per layout, in design px. The slide is drawn at 640 × 360 and scaled.
const G = {
  wide: { w: 920, h: 540, win: { x: 30, y: 30, w: 860, h: 570 }, rail: 140, pane: 220, canvas: 350, thumb: 100, step: 70, idea: 188, pad: 24 },
  // Narrow, the window keeps its size and runs off the left: the slide rail
  // goes out of frame so the slide and Designer draw at true scale, not shrunk
  compact: { w: 358, h: 400, win: { x: -78, y: 20, w: 420, h: 432 }, rail: 72, pane: 150, canvas: 220, thumb: 48, step: 44, idea: 126, pad: 14 },
}

function fit(l: Layout, pane: boolean) {
  const g = G[l]
  const editor = g.win.w - g.rail - (pane ? g.pane : 0)
  const k = Math.min((editor - g.pad * 2) / 640, (g.canvas - g.pad * 2) / 360, l === 'wide' ? 0.8 : 0.5)
  // Compact with the pane open: top-align with the second rail thumbnail rather than land a few px off it.
  const y = l === 'compact' && pane ? 12 + g.step : (g.canvas - 360 * k) / 2
  return { k, x: (editor - 640 * k) / 2, y }
}

/* ---- The slide itself ---- */

type Box = [number, number, number, number]
const LOOK: Record<Design, { photo: Box; title: [number, number]; bullets: [number, number]; light: boolean; panel: number; shade: number; rule: boolean }> = {
  plain: { photo: [360, 112, 232, 174], title: [48, 40], bullets: [56, 128], light: false, panel: 0, shade: 0, rule: false },
  split: { photo: [0, 0, 300, 360], title: [336, 128], bullets: [340, 200], light: true, panel: 1, shade: 0, rule: true },
  band: { photo: [0, 0, 640, 188], title: [48, 216], bullets: [52, 280], light: false, panel: 0, shade: 0, rule: false },
  overlay: { photo: [0, 0, 640, 360], title: [48, 222], bullets: [52, 284], light: true, panel: 0, shade: 1, rule: false },
}

const Photo = defineComponent({
  setup() {
    const id = useId().replace(/:/g, '')
    const sky = `${id}-sky`
    const sea = `${id}-sea`
    return () =>
      h(
        'svg',
        { viewBox: '0 0 640 360', preserveAspectRatio: 'xMinYMid slice', class: 'pp-photo-svg', 'aria-hidden': 'true' },
        [
          h('defs', [
            h('linearGradient', { id: sky, x1: '0', y1: '0', x2: '0', y2: '1' }, [
              h('stop', { offset: '0', 'stop-color': '#f2b58a' }),
              h('stop', { offset: '0.55', 'stop-color': '#f6d3ae' }),
              h('stop', { offset: '1', 'stop-color': '#f9e6cf' }),
            ]),
            h('linearGradient', { id: sea, x1: '0', y1: '0', x2: '0', y2: '1' }, [
              h('stop', { offset: '0', 'stop-color': '#7fa3b8' }),
              h('stop', { offset: '1', 'stop-color': '#3f6a84' }),
            ]),
          ]),
          h('rect', { width: '640', height: '360', fill: `url(#${sky})` }),
          h('circle', { cx: '430', cy: '170', r: '34', fill: '#fbe9d2' }),
          h('path', { d: 'M0 200 C 120 186 220 192 320 196 S 520 184 640 194 L640 230 L0 230Z', fill: '#b98f86' }),
          h('rect', { y: '214', width: '640', height: '146', fill: `url(#${sea})` }),
          h('path', { d: 'M0 260 C 80 236 150 226 230 232 C 280 236 300 252 320 360 L0 360Z', fill: '#c97b5a' }),
          h('path', { d: 'M0 290 C 70 270 140 262 210 270 C 250 276 270 300 280 360 L0 360Z', fill: '#a85f45' }),
          h('g', { fill: '#f3e3cf' }, [
            h('rect', { x: '40', y: '262', width: '22', height: '16', rx: '1' }),
            h('rect', { x: '76', y: '254', width: '26', height: '18', rx: '1' }),
            h('rect', { x: '118', y: '250', width: '20', height: '16', rx: '1' }),
            h('rect', { x: '150', y: '256', width: '24', height: '16', rx: '1' }),
            h('rect', { x: '24', y: '296', width: '28', height: '18', rx: '1' }),
            h('rect', { x: '70', y: '288', width: '24', height: '18', rx: '1' }),
            h('rect', { x: '112', y: '284', width: '30', height: '18', rx: '1' }),
            h('rect', { x: '160', y: '290', width: '22', height: '16', rx: '1' }),
          ]),
          h('path', { d: 'M470 236 h40 l-6 8 h-30z', fill: '#2f4f63' }),
          h('path', { d: 'M488 236 v-22 l14 20z', fill: '#f9efe2' }),
        ],
      )
  },
})

const SlideArt = defineComponent({
  props: {
    n: { type: Number, required: true },
    design: { type: String as PropType<Design>, required: true },
  },
  setup(props) {
    return () => {
      if (props.n === 1) {
        return h('div', { class: 'pp-slide', 'data-n': '1' }, [
          h('span', { class: 'pp-s1-title' }, 'Team Offsite 2026'),
          h('span', { class: 'pp-s1-sub' }),
        ])
      }
      if (props.n >= 3) {
        const rows = [
          [300, 240, 270],
          [260, 300, 200],
          [280, 220, 250],
          [240, 290, 230],
        ][(props.n - 3) % 4]
        return h('div', { class: 'pp-slide', 'data-n': 'other' }, [
          h('span', { class: 'pp-o-title', style: { width: `${[260, 300, 220, 280][(props.n - 3) % 4]}px` } }),
          ...rows.map((w, i) => h('span', { key: i, class: 'pp-o-row', style: { width: `${w}px` } })),
        ])
      }
      const L = LOOK[props.design]
      const [px, py, pw, ph] = L.photo
      return h('div', { class: 'pp-slide', 'data-light': L.light || undefined }, [
        h('div', { class: 'pp-panel', 'data-show': L.panel > 0 || undefined }),
        h('div', { class: 'pp-photo', style: { left: `${px}px`, top: `${py}px`, width: `${pw}px`, height: `${ph}px` } }, [h(Photo)]),
        h('div', { class: 'pp-shade', style: { opacity: L.shade } }),
        h('span', { class: 'pp-rule', 'data-show': L.rule || undefined }),
        h('span', { class: 'pp-title', style: { transform: `translate(${L.title[0]}px, ${L.title[1]}px)` } }, 'Lisbon, in May'),
        h(
          'div',
          { class: 'pp-bullets', style: { transform: `translate(${L.bullets[0]}px, ${L.bullets[1]}px)` } },
          [210, 168, 188].map((w, i) =>
            h('span', { key: i, class: 'pp-bullet' }, [
              h('span', { class: 'pp-dot' }),
              h('span', { class: 'pp-line', style: { width: `${w}px` } }),
            ]),
          ),
        ),
      ])
    }
  },
})

const Mini = defineComponent({
  props: {
    n: { type: Number, required: true },
    design: { type: String as PropType<Design>, required: true },
    width: { type: Number, required: true },
    style: { type: Object as PropType<CSSProperties>, required: false },
  },
  setup(props) {
    return () => {
      const k = props.width / 640
      return h(
        'div',
        { class: 'pp-mini', style: { width: `${props.width}px`, height: `${360 * k}px`, ...props.style } },
        [
          h('div', { style: { transform: `scale(${k})`, transformOrigin: '0 0' } }, [
            h(SlideArt, { n: props.n, design: props.design }),
          ]),
        ],
      )
    }
  },
})

const IDEAS: Design[] = ['band', 'split', 'overlay']

/* ---- Script ---- */

async function script(a: Act<S>) {
  // Narrow, the rail is out of frame: the story starts on slide 2
  const t = a.rect('thumb-2')
  const rail = t.x + t.width > 0
  if (!rail) a.snap({ slide: 2 })
  await a.wait(700)
  a.mark('open')
  if (rail) {
    await a.click('thumb-2')
    await a.set({ slide: 2 })
    await a.wait(1000)
  }

  a.mark('designer')
  await a.click({ at: 'designer', x: 0.5, y: 0.3 })
  await a.set({ pane: true, ideas: true })
  await a.wait(1300)

  await a.move({ at: 'idea-2', x: 0.82, y: 0.78 })
  await a.wait(400)
  a.mark('pick')
  await a.click()
  await a.set({ design: 'split', picked: 2 })
  await a.wait(2800)

  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ design: 'plain', picked: 0 })
  await a.wait(1200)
  await a.click('close')
  await a.set({ pane: false, ideas: false })
  await a.wait(900)
  if (rail) {
    await a.click('thumb-1')
    await a.set({ slide: 1 })
  }
  await a.wait(1200)
}
</script>

<template>
  <Stage
    :width="G.wide.w"
    :height="G.wide.h"
    :compact="{ below: 600, width: G.compact.w, height: G.compact.h }"
    :initial="initial"
    :poster="poster"
    :script="script"
    :cursor="{ at: 'thumb-1' }"
    accent="#c43e1c"
    class="pp-stage"
    v-slot="{ state: s, layout }"
  >
    <Window
      title="Team Offsite"
      class="pp-window"
      :data-layout="layout"
      :style="{
        left: `${G[layout].win.x}px`,
        top: `${G[layout].win.y}px`,
        width: `${G[layout].win.w}px`,
        height: `${G[layout].win.h}px`,
      }"
    >
      <!-- Tabs -->
      <div class="pp-tabs">
        <span
          v-for="(t, i) in layout === 'wide'
            ? ['Home', 'Insert', 'Draw', 'Design', 'Transitions', 'Animations', 'Slide Show', 'Review', 'View']
            : ['Home', 'Insert', 'Draw', 'Design']"
          :key="t"
          class="pp-tab"
          :data-active="i === 0 || undefined"
        >
          {{ t }}
        </span>
        <span class="pp-spacer" />
        <Bar v-if="layout === 'wide'" :w="52" :h="18" :r="5" :tone="2" />
        <span class="pp-share">
          <Bar :w="30" :h="5" :tone="1" class="pp-share-bar" />
        </span>
      </div>

      <!-- Ribbon -->
      <div class="pp-ribbon">
        <span class="pp-big">
          <ClipboardPaste :size="22" :stroke-width="1.4" />
          <Bar :w="24" :h="5" :tone="3" />
        </span>
        <span class="pp-big">
          <SquarePlus :size="22" :stroke-width="1.4" />
          <Bar :w="34" :h="5" :tone="3" />
        </span>
        <span class="pp-sep" />
        <span v-if="layout === 'wide'" class="pp-group">
          <span class="pp-row">
            <span class="pp-field" :style="{ width: '104px' }">
              <Bar :w="52" :h="5" :tone="3" />
            </span>
            <span class="pp-field" :style="{ width: '34px' }">
              <Bar :w="12" :h="5" :tone="3" />
            </span>
          </span>
          <span class="pp-row pp-icons">
            <Bold :size="15" :stroke-width="1.6" />
            <Italic :size="15" :stroke-width="1.6" />
            <Underline :size="15" :stroke-width="1.6" />
            <Strikethrough :size="15" :stroke-width="1.6" />
          </span>
        </span>
        <span v-else class="pp-group">
          <span class="pp-row pp-icons">
            <Bold :size="15" :stroke-width="1.6" />
            <Italic :size="15" :stroke-width="1.6" />
            <Underline :size="15" :stroke-width="1.6" />
          </span>
          <span class="pp-row pp-icons">
            <AlignLeft :size="15" :stroke-width="1.6" />
            <AlignCenter :size="15" :stroke-width="1.6" />
            <List :size="15" :stroke-width="1.6" />
          </span>
        </span>
        <template v-if="layout === 'wide'">
          <span class="pp-sep" />
          <span class="pp-group">
            <span class="pp-row pp-icons">
              <List :size="15" :stroke-width="1.6" />
              <ListOrdered :size="15" :stroke-width="1.6" />
            </span>
            <span class="pp-row pp-icons">
              <AlignLeft :size="15" :stroke-width="1.6" />
              <AlignCenter :size="15" :stroke-width="1.6" />
              <AlignRight :size="15" :stroke-width="1.6" />
              <AlignJustify :size="15" :stroke-width="1.6" />
            </span>
          </span>
          <span class="pp-sep" />
          <span class="pp-big">
            <Shapes :size="22" :stroke-width="1.4" />
            <Bar :w="30" :h="5" :tone="3" />
          </span>
          <span class="pp-big">
            <Layers :size="22" :stroke-width="1.4" />
            <Bar :w="32" :h="5" :tone="3" />
          </span>
        </template>
        <span class="pp-spacer" />
        <span class="pp-sep" />
        <span class="pp-designer" data-target="designer" :data-open="s.pane || undefined">
          <LayoutDashboard :size="22" :stroke-width="1.5" class="pp-designer-icon" />
          <span class="pp-designer-label">Designer</span>
        </span>
      </div>

      <!-- Main -->
      <div class="pp-main">
        <aside class="pp-rail" :style="{ width: `${G[layout].rail}px` }">
          <div
            v-for="(n, i) in [1, 2, 3, 4, 5, 6]"
            :key="n"
            class="pp-thumb"
            :style="{ top: `${12 + i * G[layout].step}px` }"
          >
            <span class="pp-num">{{ n }}</span>
            <div class="pp-thumb-box" :data-target="`thumb-${n}`" :data-selected="s.slide === n || undefined">
              <Mini :n="n" :design="n === 2 ? s.design : 'plain'" :width="G[layout].thumb" />
            </div>
          </div>
        </aside>
        <div class="pp-work" data-crop>
          <div class="pp-canvas" data-crop :style="{ height: `${G[layout].canvas}px` }">
            <div
              class="pp-fit"
              :style="{
                transform: `translate(${fit(layout, s.pane).x}px, ${fit(layout, s.pane).y}px) scale(${fit(layout, s.pane).k})`,
              }"
            >
              <div v-for="n in [1, 2]" :key="n" class="pp-page" :data-on="s.slide === n || undefined">
                <SlideArt :n="n" :design="n === 2 ? s.design : 'plain'" />
              </div>
            </div>
          </div>
          <div class="pp-notes">
            <Bar :w="layout === 'wide' ? 96 : 64" :h="5" :tone="2" />
          </div>
          <div class="pp-status">
            <Bar :w="54" :h="5" :tone="3" />
            <span class="pp-spacer" />
            <Bar :w="layout === 'wide' ? 120 : 60" :h="5" :tone="2" />
          </div>
          <aside class="pp-pane" :data-open="s.pane || undefined" :style="{ width: `${G[layout].pane}px` }">
            <div class="pp-pane-head">
              <Text class="pp-pane-title">Designer</Text>
              <span class="pp-close" data-target="close">
                <X :size="14" :stroke-width="1.8" />
              </span>
            </div>
            <div
              v-for="(d, i) in IDEAS"
              :key="d"
              class="pp-idea"
              :data-target="`idea-${i + 1}`"
              :data-show="s.ideas || undefined"
              :data-picked="s.picked === i + 1 || undefined"
              :style="{ '--d': s.ideas ? `${180 + i * 70}ms` : `${(2 - i) * 40}ms` }"
            >
              <Mini :n="2" :design="d" :width="G[layout].idea" />
            </div>
          </aside>
        </div>
      </div>
    </Window>
  </Stage>
</template>
