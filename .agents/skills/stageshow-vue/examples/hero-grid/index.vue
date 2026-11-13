<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, type CSSProperties } from 'vue'
import { Badge, Check, Icon, Roll, Segmented, Stage, Toggle, Window, type Act } from '../../kit'
import './grid.css'

// An image-led hero: one drafting surface, with four quieter pictures.
// Orange keycaps and violet glass balance the neutral sheet and dark player.
// Every tile is its own Stage. The grid never scales as one large picture.
// Only the drafting tile moves: once in view, then it holds the result.

type Draft = { tab: number; sent: 'idle' | 'busy' | 'done'; selected: boolean; gap: number }
const INITIAL: Draft = { tab: 0, sent: 'idle', selected: false, gap: 24 }
const POSTER: Draft = { tab: 1, sent: 'done', selected: true, gap: 25 }
const at = (left: number, top: number, width?: number, height?: number): CSSProperties => ({
  left: `${left}px`,
  top: `${top}px`,
  ...(width !== undefined ? { width: `${width}px` } : null),
  ...(height !== undefined ? { height: `${height}px` } : null),
})

const draft = async (a: Act<Draft>) => {
  await a.wait(650)
  await a.click({ at: 'week', x: 0.82, y: 0.75 })
  await a.set({ tab: 1 })
  await a.wait(450)
  await a.click({ at: 'publish', x: 0.85, y: 0.7 })
  await a.set({ sent: 'busy' })
  await a.wait(800)
  await a.set({ sent: 'done' })
  await a.wait(650)
  await a.click({ at: 'frame', x: 0.7, y: 0.7 })
  await a.set({ selected: true })
  await a.wait(650)
  await a.click('plus')
  await a.set({ gap: 25 })
  await a.wait(650)
  await a.move({ x: -30, y: 180 }, { duration: 700 })
}

const KEY_ROWS = [
  [['Q', 'た'], ['W', 'て'], ['E', 'い'], ['R', 'す'], ['T', 'か']],
  [['A', 'ち'], ['S', 'と'], ['D', 'し'], ['F', 'は'], ['G', 'き']],
  [['Z', 'つ'], ['X', 'さ'], ['C', 'そ'], ['V', 'ひ'], ['B', 'こ']],
]

// Choose a substantial crop through a blank cap edge, never a narrow sliver.
function keySize(w: number, h: number) {
  for (let size = 36; size <= 48; size++) {
    const gap = Math.round(size * 0.17)
    const part = (length: number) => (length - Math.floor((length + gap) / (size + gap)) * (size + gap)) / size
    if (part(w - 14) >= 0.4 && part(w - 14) <= 0.75 && part(h - 14) >= 0.38 && part(h - 14) <= 0.75) return { size, gap }
  }
  return { size: 40, gap: 7 }
}

const MARKS = [
  ['#0a7cff', 'M12 4.5c4.7 0 8.5 3 8.5 6.8S16.7 18 12 18c-.9 0-1.8-.1-2.6-.3L5.2 19.6l1.2-3.4C4.6 14.9 3.5 13.2 3.5 11.3 3.5 7.5 7.3 4.5 12 4.5Z'],
  ['#fff', 'calendar'],
  ['#ff9500', 'M13.2 2.8 5.6 13.1a.8.8 0 0 0 .64 1.27H11l-1.2 6.8 7.6-10.3a.8.8 0 0 0-.64-1.27H12l1.2-6.8Z'],
  ['#1c1c1e', 'M7.4 5.2v12.8a.9.9 0 0 0 1.37.77l10.2-6.4a.9.9 0 0 0 0-1.54L8.77 4.43A.9.9 0 0 0 7.4 5.2Z'],
  ['#2fc455', 'M12 2.8a7 7 0 0 1 7 7c0 5-7 11.6-7 11.6S5 14.8 5 9.8a7 7 0 0 1 7-7Zm0 4.2a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6Z'],
  ['#7a5cff', 'M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 17.5Zm3.5 2.3v1.6h7V8.8Zm0 3.6v1.6h7v-1.6Zm0 3.6v1.6h4.4V16Z'],
  ['#ff3b45', 'M12 20s-7.5-4.6-7.5-10.1A4.4 4.4 0 0 1 12 7.1a4.4 4.4 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20Z'],
  ['#2bb3f0', 'M4 8.2A2.2 2.2 0 0 1 6.2 6h1.6l1.3-1.6h5.8L16.2 6h1.6A2.2 2.2 0 0 1 20 8.2v8.6a2.2 2.2 0 0 1-2.2 2.2H6.2A2.2 2.2 0 0 1 4 16.8Zm8 1.3a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8Z'],
  ['#ffcc00', 'M6 5h12v2.4H6Zm0 4.8h12v2.4H6Zm0 4.8h8v2.4H6Z'],
  ['#1c1c1e', 'M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Zm-.9 4v5.2l4.3 2.6.9-1.5-3.4-2V7.5Z'],
  ['#1fb38a', 'M5 11.2 10 16l9-9.2-1.7-1.6L10 12.7 6.7 9.5Z'],
  ['#ff6a3d', 'M7 4h10a1 1 0 0 1 1 1v15.2l-6-3.6-6 3.6V5a1 1 0 0 1 1-1Z'],
]

type TileKind = 'drafting' | 'revenue' | 'keys' | 'icons' | 'player'
type Tile = { name: string; x: number; y: number; w: number; h: number; kind: TileKind }

function composition(w: number): Tile[] {
  const gap = 8
  const heroH = w >= 520 ? Math.round((w * 9) / 16) : 332
  if (w >= 520) {
    const narrow = 172
    const wide = w - narrow - gap
    const row = 180
    return [
      { name: 'Drafting controls', x: 0, y: 0, w, h: heroH, kind: 'drafting' },
      { name: 'Revenue on glass', x: 0, y: heroH + gap, w: wide, h: row, kind: 'revenue' },
      { name: 'Keyboard detail', x: wide + gap, y: heroH + gap, w: narrow, h: 126, kind: 'keys' },
      { name: 'Icon collection', x: wide + gap, y: heroH + 142, w: narrow, h: row * 2 - 126, kind: 'icons' },
      { name: 'Music player', x: 0, y: heroH + row + gap * 2, w: wide, h: row, kind: 'player' },
    ]
  }
  const narrow = Math.floor((w - gap) / 2)
  return [
    { name: 'Drafting controls', x: 0, y: 0, w, h: heroH, kind: 'drafting' },
    { name: 'Keyboard detail', x: 0, y: heroH + gap, w: narrow, h: 140, kind: 'keys' },
    { name: 'Icon collection', x: narrow + gap, y: heroH + gap, w: w - narrow - gap, h: 140, kind: 'icons' },
    { name: 'Revenue on glass', x: 0, y: heroH + 156, w, h: 230, kind: 'revenue' },
    { name: 'Music player', x: 0, y: heroH + 394, w, h: 196, kind: 'player' },
  ]
}

const rootRef = ref<HTMLDivElement | null>(null)
const width = ref(0)
let observer: ResizeObserver | null = null

onMounted(() => {
  const element = rootRef.value
  if (!element) return
  const measure = () => {
    width.value = Math.floor(element.getBoundingClientRect().width)
  }
  measure()
  observer = new ResizeObserver(measure)
  observer.observe(element)
})

onUnmounted(() => {
  observer?.disconnect()
})

const tiles = computed(() => (width.value ? composition(width.value) : []))
const height = computed(() => (tiles.value.length ? Math.max(...tiles.value.map((t) => t.y + t.h)) : 0))
</script>

<template>
  <div ref="rootRef" class="hero-grid" :style="{ height: height ? `${height}px` : undefined }" aria-label="A hero grid of product details">
    <figure v-for="t in tiles" :key="t.name" class="hg-tile" :aria-label="t.name" :style="at(t.x, t.y, t.w, t.h)">
      <!-- Drafting -->
      <Stage
        v-if="t.kind === 'drafting'"
        :width="t.w < 520 ? t.w : 480"
        :height="t.w < 520 ? t.h : 270"
        fill
        :initial="INITIAL"
        :poster="POSTER"
        play="once"
        :script="draft"
        :cursor="{ at: { x: -30, y: 180 }, style: 'large', idle: false }"
        class="hg-draft"
        v-slot="{ state: s }"
      >
        <div class="hg-draft-sheet" :data-compact="t.w < 520 || undefined">
          <Segmented
            class="hg-segments"
            :style="t.w < 520 ? at(16, 16, t.w - 32, 44) : at(16, 16, 204, 48)"
            :items="['Day', 'Week', 'Month']"
            :value="s.tab"
            :targets="[undefined, 'week', undefined]"
            cursor="hand"
          />
          <span class="hg-switch" :style="t.w < 520 ? at(t.w - 64, 281) : at(234, 27)"><Toggle on /></span>
          <div class="hg-stepper" :style="t.w < 520 ? at(16, 270, 160, 46) : at(298, 16, 166, 48)">
            <span class="hg-secondary">Gap</span><span class="hg-stepper-key">−</span>
            <Roll class="hg-gap">{{ String(s.gap) }}</Roll>
            <span class="hg-stepper-key" data-target="plus" data-cursor="hand"><Icon name="plus" :size="16" :stroke="2" /></span>
          </div>
          <div class="hg-search" :style="t.w < 520 ? at(16, 76, t.w - 152, 44) : at(16, 80, 168, 48)">
            <Icon name="search" :size="t.w < 520 ? 16 : 18" /><span>Search</span>
          </div>
          <div class="hg-task-list" :style="t.w < 520 ? at(16, 136, 120, 118) : at(16, 144, 168, 150)" :data-crop="t.w >= 520 || undefined">
            <span v-for="(label, i) in ['Design', 'Build', 'Ship']" :key="label" class="hg-task">
              <Check :on="i < 2" :size="18" />{{ label }}
            </span>
          </div>
          <span class="hg-publish" data-target="publish" data-cursor="hand" :style="t.w < 520 ? at(t.w - 120, 76, 104, 44) : at(336, 86, 128, 48)">
            <!-- Each state is a centered layer in one cell, crossfading:
                 Publish, then the pending check alone, then the done check
                 with Live. Nothing resizes or slides across the button -->
            <span class="hg-layer" :data-on="s.sent === 'idle' || undefined">Publish</span>
            <span class="hg-layer" :data-on="s.sent === 'busy' || undefined"><Check :on="false" pending :size="18" /></span>
            <span class="hg-layer" :data-on="s.sent === 'done' || undefined"><Check :on="s.sent === 'done'" :size="18" />Live</span>
          </span>
          <div
            class="hg-design-frame"
            data-target="frame"
            data-cursor="crosshair"
            :data-selected="s.selected || undefined"
            :style="t.w < 520 ? at(160, 158, t.w - 180, 62) : at(208, 98, 104, 84)"
          >
            <span class="hg-frame-name">Frame</span>
            <span class="hg-frame-detail" :data-on="s.selected || undefined">
              <span v-for="i in [0, 1, 2, 3]" :key="i" class="hg-frame-handle" :data-corner="i" />
              <span class="hg-frame-size">{{ t.w < 520 ? t.w - 180 : 104 }} × {{ t.w < 520 ? 62 : 84 }}</span>
            </span>
          </div>
          <template v-if="t.w >= 520">
            <div class="hg-slider" :style="at(344, 168, 160, 6)" data-crop><span /><i /></div>
            <div class="hg-frequency" :style="at(200, 210, 128, 48)">Weekly<Icon name="chevron-down" :size="18" /></div>
            <span class="hg-wheel-button" :style="at(344, 210, 48, 48)"><span /></span>
            <span class="hg-people" :style="at(408, 207)" data-crop><span>A</span><span aria-hidden="true" /><span aria-hidden="true" /></span>
          </template>
        </div>
      </Stage>

      <!-- Revenue -->
      <Stage v-else-if="t.kind === 'revenue'" :width="t.w" :height="t.h" theme="glass" accent="#5b5bf6" class="hg-revenue">
        <Window chrome="glass" lights="white" url="studio.example" class="hg-revenue-window" :style="at(20, 20, Math.max(310, t.w + 12), t.h + 40)" :body="{ 'data-crop': '' }">
          <div class="hg-revenue-body">
            <div class="hg-revenue-head"><strong>$12,480</strong><Badge tone="success">+18%</Badge></div>
            <svg :width="Math.min(300, t.w - 76)" :height="Math.max(48, t.h - 136)" viewBox="0 0 300 100" preserveAspectRatio="none" class="hg-chart" aria-label="Revenue trending upward">
              <path d="M4 90C18 90 26 72 40 74S62 88 78 64 100 74 117 50 143 65 160 38 184 56 203 26 229 41 249 20 276 32 296 8" />
              <circle cx="296" cy="8" r="3.5" />
            </svg>
          </div>
        </Window>
      </Stage>

      <!-- Keys -->
      <Stage v-else-if="t.kind === 'keys'" :width="t.w" :height="t.h" class="hg-keys">
        <div
          class="hg-keyboard"
          :style="{ '--hg-key': `${keySize(t.w, t.h).size}px`, '--hg-key-gap': `${keySize(t.w, t.h).gap}px` } as CSSProperties"
          data-crop
        >
          <div v-for="(row, y) in KEY_ROWS" :key="y" class="hg-key-row">
            <span v-for="([latin, kana], x) in row" :key="latin" class="hg-key">
              <template
                v-if="
                  14 + x * (keySize(t.w, t.h).size + keySize(t.w, t.h).gap) + keySize(t.w, t.h).size <= t.w &&
                  14 + y * (keySize(t.w, t.h).size + keySize(t.w, t.h).gap) + keySize(t.w, t.h).size <= t.h
                "
              >
                <small>{{ latin }}</small><span>{{ kana }}</span>
              </template>
            </span>
          </div>
        </div>
      </Stage>

      <!-- Icons -->
      <Stage v-else-if="t.kind === 'icons'" :width="t.w" :height="t.h" class="hg-icons">
        <div class="hg-icon-grid" data-crop>
          <span
            v-for="([background, glyph], i) in MARKS"
            :key="i"
            class="hg-app-icon"
            :style="{ background, color: i === 8 ? '#6b4e00' : '#fff' }"
          >
            <span v-if="glyph === 'calendar'" class="hg-calendar"><small>FRI</small>24</span>
            <svg v-else viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
              <path :d="glyph" fill="currentColor" fill-rule="evenodd" />
            </svg>
          </span>
        </div>
      </Stage>

      <!-- Player -->
      <Stage v-else-if="t.kind === 'player'" :width="t.w" :height="t.h" theme="dark" class="hg-player">
        <div
          class="hg-player-content"
          :data-stack="t.w - 40 - (t.h - 40) - 18 < 136 || undefined"
          :style="{ '--hg-cover': `${t.w - 40 - (t.h - 40) - 18 < 136 ? 48 : t.h - 40}px` } as CSSProperties"
        >
          <span class="hg-cover" aria-label="Graphic album artwork"><span class="hg-cover-sun" /><span class="hg-cover-sea" /></span>
          <div class="hg-player-side">
            <span class="hg-player-names"><strong>Low Tide</strong><span>Marlo</span></span>
            <span class="hg-player-progress"><span class="hg-player-rail"><i /></span><span class="hg-player-times"><span>2:38</span><span>2:48</span></span></span>
            <span class="hg-player-controls" aria-label="Playback paused">
              <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true"><path d="M3.2 3h1.6v10H3.2zM13 3.7v8.6a.7.7 0 0 1-1.07.6L5.6 8.6a.7.7 0 0 1 0-1.2l6.33-4.3A.7.7 0 0 1 13 3.7Z" /></svg>
              <span class="hg-player-play"><svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M5 2.8v10.4L13 8Z" /></svg></span>
              <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true"><path d="M11.2 3h1.6v10h-1.6zM3 3.7v8.6a.7.7 0 0 0 1.07.6l6.33-4.3a.7.7 0 0 0 0-1.2L4.07 3.1A.7.7 0 0 0 3 3.7Z" /></svg>
            </span>
          </div>
        </div>
      </Stage>
    </figure>
  </div>
</template>
