<script setup lang="ts">
import { Eye, Frame, Image as ImageIcon, MessageCircle, Minus, MousePointer2, PenTool, Pipette, Plus, Square, Type, X } from 'lucide-vue-next'
import { Bar, Facepile, Follow, Popover, Stage, Text, Window, type Act, type Point, type Rect, type Layout, BrandMark } from '../../kit'
import './figma.css'

// Figma: select a button layer, drag its fill's hue in the color picker and
// watch the button change live, while Maya's cursor drifts around nearby.
// Loops by undoing the change (cmd+z) and deselecting.

type S = {
  hover: boolean
  selected: boolean
  picker: boolean
  hue: number
  dragging: boolean
  /** Maya's cursor; null is her resting spot */
  maya: Point | null
}

// The fill keeps its saturation and brightness; only the hue is dragged
const SAT = 0.66
const VAL = 0.97
const HUE_FROM = 252
const HUE_TO = 336

function hex(h: number) {
  const f = (n: number) => {
    const k = (n + h / 60) % 6
    return VAL - VAL * SAT * Math.max(0, Math.min(k, 4 - k, 1))
  }
  return [f(5), f(3), f(1)].map((c) => Math.round(c * 255).toString(16).padStart(2, '0')).join('').toUpperCase()
}

// Maya's cursor waypoints, in canvas fractions resolved against the canvas rect
const MAYA = {
  rest: { x: 0.8, y: 0.3 },
  a: { x: 0.86, y: 0.46 },
  b: { x: 0.74, y: 0.36 },
  c: { x: 0.6, y: 0.1 },
  d: { x: 0.47, y: 0.13 },
  e: { x: 0.62, y: 0.27 },
}

const initial: S = { hover: false, selected: false, picker: false, hue: HUE_FROM, dragging: false, maya: null }

function mayaAt(c: { x: number; y: number; width: number; height: number }, p: Point): Point {
  return { x: c.x + c.width * p.x, y: c.y + c.height * p.y }
}

function boxPx(r: Rect) {
  return { left: `${r.x}px`, top: `${r.y}px`, width: `${r.width}px`, height: `${r.height}px` }
}

function pickerStyle(rect: (name: string) => Rect, layout: Layout) {
  const fill = rect('fill-row')
  const props = rect('props')
  return layout === 'compact'
    ? { left: `${props.x + 8}px`, top: `${fill.y + fill.height + 6}px`, width: `${props.width - 16}px` }
    : { left: `${props.x - 8 - 220}px`, top: `${Math.min(fill.y - 10, 480 - 24 - 244)}px`, width: '220px' }
}

async function script(a: Act<S>) {
  const maya = (p: Point) => a.set({ maya: mayaAt(a.rect('canvas'), p) })
  await a.wait(500)
  maya(MAYA.a)

  // 1. Select the button on the canvas
  a.mark('select')
  await a.move({ at: 'button', x: 0.82, y: 0.7 })
  await a.set({ hover: true })
  await a.wait(350)
  await a.click()
  await a.set({ hover: false, selected: true })
  maya(MAYA.b)
  await a.wait(900)

  // 2. Open its fill
  a.mark('fill')
  await a.move('fill-swatch')
  await a.wait(150)
  await a.click()
  await a.set({ picker: true })
  maya(MAYA.c)
  await a.wait(700)

  // 3. Drag the hue; the button follows live
  a.mark('drag')
  await a.move('hue-thumb')
  await a.wait(200)
  const track = a.rect('hue-track')
  const span = track.width - 12
  const end = { x: track.x + 6 + (span * HUE_TO) / 360, y: track.y + track.height / 2 }
  await a.drag(end, (at) => {
    const t = Math.max(0, Math.min(1, (at.x - track.x - 6) / span))
    a.put({ dragging: true, hue: Math.max(HUE_FROM, t * 360) })
  })
  await a.set({ dragging: false, hue: HUE_TO })
  maya(MAYA.d)
  await a.wait(900)

  // 4. Click away: the picker closes, the change holds
  a.mark('done')
  await a.click('blank')
  await a.set({ picker: false, selected: false })
  maya(MAYA.e)
  await a.wait(2200)

  // 5. Undo, so the loop starts where it began
  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ hue: HUE_FROM })
  a.set({ maya: null })
  await a.wait(1600)
}

const LAYERS: { depth: number; icon: 'frame' | 'type' | 'image' | 'rect'; w: number; name?: string }[] = [
  { depth: 0, icon: 'frame', w: 46 },
  { depth: 1, icon: 'rect', w: 28 },
  { depth: 1, icon: 'frame', w: 36 },
  { depth: 2, icon: 'type', w: 52 },
  { depth: 2, icon: 'type', w: 40 },
  { depth: 2, icon: 'frame', w: 0, name: 'Button' },
  { depth: 2, icon: 'image', w: 34 },
  { depth: 0, icon: 'frame', w: 40 },
  { depth: 0, icon: 'frame', w: 50 },
  { depth: 0, icon: 'frame', w: 38 },
]

function layerIconComp(kind: (typeof LAYERS)[number]['icon']) {
  if (kind === 'type') return Type
  if (kind === 'image') return ImageIcon
  if (kind === 'rect') return Square
  return Frame
}
</script>

<template>
  <Stage
    :width="860"
    :height="480"
    :initial="initial"
    :script="script"
    :cursor="{ at: 'blank' }"
    :compact="{ below: 600, width: 358, height: 440 }"
    accent="#0D99FF"
    class="fg"
    v-slot="{ state: s, rect, layout }"
  >
    <Window
      class="fg-window"
      :data-layout="layout"
    >
      <template #lead>
        <span class="fg-tools">
          <BrandMark brand="figma" :tile="false" :size="16" :width="11" class="fg-mark" />
          <span class="fg-tool" data-active>
            <MousePointer2 :size="14" :stroke-width="1.6" />
          </span>
          <span class="fg-tool">
            <Frame :size="14" :stroke-width="1.6" />
          </span>
          <span class="fg-tool">
            <Square :size="14" :stroke-width="1.6" />
          </span>
          <span class="fg-tool">
            <PenTool :size="14" :stroke-width="1.6" />
          </span>
          <span class="fg-tool">
            <Type :size="14" :stroke-width="1.6" />
          </span>
          <span v-if="layout === 'wide'" class="fg-tool">
            <MessageCircle :size="14" :stroke-width="1.6" />
          </span>
        </span>
      </template>

      <template #toolbar>
        <span class="fg-share-row">
          <Facepile :names="['Maya', 'Ana']" :size="22" :tones="['success', 'accent']" />
          <span class="fg-share">Share</span>
        </span>
      </template>

      <div class="fg-body">
        <aside v-if="layout === 'wide'" class="fg-layers" data-crop>
          <div class="fg-file">
            <Text class="fg-file-name">Landing page</Text>
            <Bar :w="44" :h="5" :tone="3" />
          </div>
          <div class="fg-tabs">
            <Bar :w="34" :h="6" :tone="5" />
            <Bar :w="30" :h="6" :tone="3" />
          </div>
          <div class="fg-tree">
            <div
              v-for="(l, i) in LAYERS"
              :key="i"
              class="fg-layer"
              :data-depth="l.depth"
              :data-selected="(l.name && s.selected) || undefined"
              :data-parent="(i === 0 || i === 2) && s.selected ? true : undefined"
              :style="{ paddingLeft: `${10 + l.depth * 14}px` }"
            >
              <component :is="layerIconComp(l.icon)" :size="13" :stroke-width="1.6" class="fg-icon" />
              <Text v-if="l.name" class="fg-layer-name">{{ l.name }}</Text>
              <Bar v-else :w="l.w" :h="5" :tone="l.depth === 0 ? 4 : 3" />
            </div>
          </div>
        </aside>

        <div class="fg-canvas" data-target="canvas" data-crop>
          <div class="fg-frames">
            <div class="fg-frame-wrap fg-desktop">
              <Text class="fg-frame-label">Desktop</Text>
              <div class="fg-frame">
                <div class="fg-nav">
                  <Bar :w="12" :h="12" :r="4" :tone="5" />
                  <span class="fg-nav-links">
                    <Bar :w="22" :h="4" :tone="3" />
                    <Bar :w="18" :h="4" :tone="3" />
                    <Bar :w="24" :h="4" :tone="3" />
                  </span>
                  <Bar :w="30" :h="12" :r="6" :tone="2" />
                </div>
                <div class="fg-hero">
                  <div class="fg-hero-copy">
                    <Bar :w="118" :h="9" :r="3" :tone="5" />
                    <Bar :w="84" :h="9" :r="3" :tone="5" />
                    <div class="fg-sub">
                      <Bar :w="112" :h="4" :tone="3" />
                      <Bar :w="90" :h="4" :tone="3" />
                    </div>
                    <div class="fg-buttons">
                      <span
                        class="fg-cta"
                        data-target="button"
                        :data-dragging="s.dragging || undefined"
                        :style="{ background: `#${hex(s.hue)}` }"
                      >
                        <span class="fg-cta-label" />
                      </span>
                      <Bar :w="46" :h="22" :r="6" :tone="2" />
                    </div>
                  </div>
                  <div class="fg-hero-art" data-crop>
                    <span class="fg-art-sun" />
                    <span class="fg-art-hill" />
                  </div>
                </div>
                <div class="fg-logos">
                  <Bar v-for="(w, i) in [30, 24, 34, 26]" :key="i" :w="w" :h="5" :tone="2" />
                </div>
              </div>
            </div>

            <div class="fg-frame-wrap fg-mobile">
              <Bar class="fg-frame-label-bar" :w="30" :h="5" :tone="3" />
              <div class="fg-frame">
                <div class="fg-nav">
                  <Bar :w="10" :h="10" :r="3" :tone="5" />
                  <Bar :w="12" :h="4" :tone="3" />
                </div>
                <Bar :w="64" :h="7" :r="3" :tone="5" />
                <Bar :w="48" :h="7" :r="3" :tone="5" :style="{ marginTop: '7px' }" />
                <div class="fg-sub">
                  <Bar :w="70" :h="4" :tone="3" />
                  <Bar :w="56" :h="4" :tone="3" />
                </div>
                <Bar :w="52" :h="18" :r="5" :tone="4" :style="{ marginTop: '10px' }" />
                <div class="fg-mobile-art" />
              </div>
            </div>

            <div class="fg-frame-wrap fg-row2">
              <Bar class="fg-frame-label-bar" :w="36" :h="5" :tone="3" />
              <div class="fg-frame">
                <Bar :w="90" :h="8" :r="3" :tone="5" />
                <div class="fg-cards">
                  <span v-for="i in [0, 1, 2]" :key="i" class="fg-card" />
                </div>
              </div>
            </div>
          </div>
          <div class="fg-blank" data-target="blank" />
        </div>

        <aside class="fg-props" data-target="props" data-crop>
          <div class="fg-props-tabs">
            <Bar :w="34" :h="6" :tone="5" />
            <Bar :w="44" :h="6" :tone="3" />
            <span class="fg-zoom">
              <Bar :w="22" :h="5" :tone="3" />
            </span>
          </div>
          <div class="fg-props-body">
            <!-- Nothing selected: the page -->
            <div class="fg-props-layer" :data-show="!s.selected || undefined">
              <section class="fg-section">
                <div class="fg-section-head">
                  <Bar :w="28" :h="6" :tone="5" />
                </div>
                <div class="fg-row">
                  <span class="fg-field fg-field-wide">
                    <span class="fg-swatch" :style="{ background: '#F5F5F5' }" />
                    <Bar :w="44" :h="5" :tone="4" />
                    <Bar :w="20" :h="5" :tone="3" :style="{ marginLeft: 'auto' }" />
                  </span>
                </div>
              </section>
              <section v-for="(w, i) in [44, 36, 40]" :key="i" class="fg-section">
                <div class="fg-section-head">
                  <Bar :w="w" :h="6" :tone="5" />
                  <Plus :size="13" :stroke-width="1.6" class="fg-icon" />
                </div>
              </section>
            </div>

            <!-- The button -->
            <div class="fg-props-layer" :data-show="s.selected || undefined">
              <section v-if="layout === 'wide'" class="fg-section">
                <div class="fg-section-head">
                  <Bar :w="40" :h="6" :tone="5" />
                </div>
                <div class="fg-row fg-pair">
                  <span class="fg-field">
                    <Bar :w="7" :h="5" :tone="3" />
                    <Bar :w="26" :h="5" :tone="4" />
                  </span>
                  <span class="fg-field">
                    <Bar :w="7" :h="5" :tone="3" />
                    <Bar :w="20" :h="5" :tone="4" />
                  </span>
                </div>
                <div class="fg-row fg-pair">
                  <span class="fg-field">
                    <Bar :w="7" :h="5" :tone="3" />
                    <Bar :w="22" :h="5" :tone="4" />
                  </span>
                  <span class="fg-field">
                    <Bar :w="7" :h="5" :tone="3" />
                    <Bar :w="18" :h="5" :tone="4" />
                  </span>
                </div>
              </section>
              <section class="fg-section">
                <div class="fg-section-head">
                  <Text class="fg-section-title">Fill</Text>
                  <Plus :size="13" :stroke-width="1.6" class="fg-icon" />
                </div>
                <div class="fg-row" data-target="fill-row">
                  <span class="fg-field fg-field-wide" :data-open="s.picker || undefined">
                    <span
                      class="fg-swatch"
                      data-target="fill-swatch"
                      :style="{ background: `#${hex(s.hue)}` }"
                      :data-dragging="s.dragging || undefined"
                    />
                    <span class="fg-hex">{{ hex(s.hue) }}</span>
                    <Bar :w="20" :h="5" :tone="3" :style="{ marginLeft: 'auto' }" />
                  </span>
                  <Eye :size="13" :stroke-width="1.6" class="fg-icon" />
                  <Minus :size="13" :stroke-width="1.6" class="fg-icon" />
                </div>
              </section>
              <section v-for="(w, i) in [38, 42, 36]" :key="i" class="fg-section">
                <div class="fg-section-head">
                  <Bar :w="w" :h="6" :tone="5" />
                  <Plus :size="13" :stroke-width="1.6" class="fg-icon" />
                </div>
              </section>
            </div>
          </div>
        </aside>
      </div>
    </Window>

    <!-- Hover and selection on the canvas, from the measured button -->
    <div class="fg-hover" :data-show="(s.hover && !s.selected) || undefined" :style="boxPx(rect('button'))" />
    <div class="fg-select" :data-show="s.selected || undefined" :style="boxPx(rect('button'))">
      <i data-c="tl" />
      <i data-c="tr" />
      <i data-c="bl" />
      <i data-c="br" />
    </div>

    <!-- Maya, on the canvas with us -->
    <Follow class="fg-maya" :to="{ ...(s.maya ?? mayaAt(rect('canvas'), MAYA.rest)), width: 0, height: 0 }" :stiffness="0.012">
      <svg width="16" height="17" viewBox="0 0 16 17" class="fg-maya-arrow" aria-hidden="true">
        <path d="M1.5 1.5 14 7.2l-5.6 1.6-2.3 5.6Z" />
      </svg>
      <span class="fg-maya-name">Maya</span>
    </Follow>

    <!-- The color picker, beside the properties panel -->
    <Popover
      :show="s.picker"
      origin="top right"
      class="fg-picker"
      :data-layout="layout"
      :style="pickerStyle(rect, layout)"
    >
      <div class="fg-picker-head">
        <Bar :w="40" :h="6" :tone="5" />
        <Bar :w="42" :h="6" :tone="3" />
        <X :size="13" :stroke-width="1.6" class="fg-icon fg-picker-x" />
      </div>
      <div class="fg-picker-body">
        <div class="fg-sv" data-crop :style="{ ['--hue' as string]: `hsl(${s.hue} 100% 50%)` }">
          <span
            class="fg-sv-knob"
            :style="{
              left: `${SAT * 100}%`,
              top: `${(1 - VAL) * 100}%`,
              background: `#${hex(s.hue)}`,
            }"
          />
        </div>
        <div class="fg-sliders">
          <Pipette :size="14" :stroke-width="1.6" class="fg-icon" />
          <div class="fg-tracks">
            <div class="fg-hue" data-target="hue-track">
              <span
                class="fg-hue-thumb"
                data-target="hue-thumb"
                :style="{ left: `calc(6px + (100% - 12px) * ${s.hue / 360})` }"
              />
            </div>
            <div class="fg-alpha" :style="{ ['--c' as string]: `#${hex(s.hue)}` }">
              <span class="fg-hue-thumb" :style="{ left: 'calc(100% - 6px)' }" />
            </div>
          </div>
        </div>
        <div class="fg-picker-hex">
          <span class="fg-field fg-field-sm">
            <Bar :w="20" :h="5" :tone="4" />
          </span>
          <span class="fg-field fg-field-grow">
            <span class="fg-hex">{{ hex(s.hue) }}</span>
            <Bar :w="20" :h="5" :tone="3" :style="{ marginLeft: 'auto' }" />
          </span>
        </div>
      </div>
    </Popover>
  </Stage>
</template>
