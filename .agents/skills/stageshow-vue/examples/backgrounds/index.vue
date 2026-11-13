<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive } from 'vue'
import { Icon, Stage } from '../../kit'
import './backgrounds.css'

// The object stays constant so the ground's contribution is easy to see.
// These are authored examples, not a fixed set of themes or presets.
const studies = [
  { id: 'diagonal', title: 'Diagonal gradient', note: 'Violet moves through pink into coral. A white surface keeps the content quiet.' },
  { id: 'radial', title: 'Radial light', note: 'A broad yellow light meets orange and rose at the edges, without a glow around the card.' },
  { id: 'mesh', title: 'Blended color fields', note: 'Mint, blue and violet meet in large fields. Their lightness changes gradually behind the UI.' },
  { id: 'night', title: 'Color on dark', note: 'Teal and magenta light sit at opposite edges. The clear foreground holds its contrast.' },
  { id: 'bands', title: 'Bands and glass', note: 'Broad ink-blue and cobalt bands leave a narrow pale edge. Their tint stays visible through the glass.' },
  { id: 'spectrum', title: 'Multicolor sweep', note: 'A wide sweep connects cool and warm hues. The card supplies one stable reading area.' },
  { id: 'tint', title: 'Tint', note: 'Lavender gives a white surface enough separation without a heavy shadow.' },
  { id: 'field', title: 'Two color fields', note: 'A warm band and a cool field meet behind the card, away from its content.' },
  { id: 'dots', title: 'Dot grid', note: 'A fine dot grid, fading out toward the edges, gives a canvas feel. The dots stay lighter than any line in the card.' },
  { id: 'halftone', title: 'Halftone', note: 'Dots grow toward one corner and vanish toward the card, so the texture frames the UI rather than sitting under it.' },
  { id: 'blueprint', title: 'Blueprint', note: 'Major and minor rules on deep blue. Two weights of line give scale; the white card is the only solid thing.' },
  { id: 'grain', title: 'Grain', note: 'A soft two-color gradient with fine grain over it, so the color reads as a material, not a screen fill.' },
  { id: 'conic', title: 'Conic sweep', note: 'Color turns around a point off the card’s corner. The sweep gives direction without a hard band.' },
  { id: 'stripes', title: 'Fine stripes', note: 'Hairline diagonals on a pale ground: texture you feel more than see, quieter than the card’s own divider.' },
  { id: 'light', title: 'Soft light', note: 'Sage, peach and cream share a light value, with a calm center for the UI.' },
  { id: 'grid', title: 'Grid', note: 'Fine blue rules establish scale. Their contrast stays below the product’s.' },
  { id: 'architecture', title: 'Architectural lines', note: 'A few precise edges give the scene direction without filling every gap.' },
  { id: 'dark', title: 'Dark material', note: 'A lifted graphite surface separates from the ground through value and edge light.' },
  { id: 'paper', title: 'Warm paper', note: 'Low contrast fibers and a warm shadow support a quiet, tangible surface.' },
  { id: 'graphic', title: 'Graphic geometry', note: 'Ink, ochre and pale blue frame the object with deliberate, substantial crops.' },
] as const

// A real halftone: one dot per cell on a 10px grid, each sized by its distance
// from the top right corner, down to nothing before it reaches the card
const halftoneDots: { x: number; y: number; r: number }[] = []
for (let y = 5; y < 252; y += 10) {
  for (let x = 5; x < 400; x += 10) {
    const d = Math.hypot(400 - x, y) / 260
    const r = 3.4 * (1 - d) ** 1.4
    if (r > 0.35) halftoneDots.push({ x, y, r })
  }
}

const widths = reactive<Record<string, number>>(
  Object.fromEntries(studies.map(s => [s.id, 288])),
)
const pictureRefs = new Map<string, HTMLDivElement>()

function setPictureRef(id: string, el: any) {
  if (el instanceof HTMLDivElement) pictureRefs.set(id, el)
  else pictureRefs.delete(id)
}

const observers: ResizeObserver[] = []
onMounted(() => {
  for (const study of studies) {
    const node = pictureRefs.get(study.id)
    if (!node) continue
    const measure = () => {
      widths[study.id] = node.clientWidth
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    observers.push(observer)
  }
})
onBeforeUnmount(() => {
  observers.forEach(o => o.disconnect())
})
</script>

<template>
  <div class="bg-gallery">
    <header class="bg-intro">
      <h1>Backgrounds</h1>
      <p>The same interface on twenty different grounds.</p>
    </header>
    <div class="bg-grid">
      <article v-for="study in studies" :key="study.id" class="bg-study" :data-study="study.id">
        <div :ref="(el) => setPictureRef(study.id, el)" class="bg-picture">
          <Stage specimen :width="widths[study.id]" :height="252" :theme="study.id === 'dark' ? 'dark' : 'light'">
            <div :class="`bg-ground bg-ground--${study.id}`" data-crop>
              <svg
                v-if="study.id === 'architecture'"
                class="bg-lines"
                width="100%"
                height="100%"
                viewBox="0 0 400 252"
                preserveAspectRatio="xMidYMid slice"
                aria-hidden="true"
              >
                <path d="M-40 204 114 50H390V-30M-16 228 138 74H414M8 252 162 98H438" />
                <path d="M114 50v202M390 50 276 164H0" />
              </svg>
              <div v-if="study.id === 'graphic'" class="bg-geometry" aria-hidden="true"><span /><i /></div>
              <svg
                v-if="study.id === 'halftone'"
                class="bg-halftone"
                width="100%"
                height="100%"
                viewBox="0 0 400 252"
                preserveAspectRatio="xMaxYMin slice"
                aria-hidden="true"
              >
                <circle v-for="(d, i) in halftoneDots" :key="i" :cx="d.x" :cy="d.y" :r="d.r" />
              </svg>
              <svg v-if="study.id === 'grain'" class="bg-grain" width="100%" height="100%" aria-hidden="true">
                <filter id="bg-grain">
                  <feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="2" stitchTiles="stitch" />
                  <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.55 0" />
                </filter>
                <rect width="100%" height="100%" filter="url(#bg-grain)" />
              </svg>
              <div class="bg-digest">
                <div class="bg-digest-heading">
                  <span class="bg-digest-icon"><Icon name="calendar" :size="18" /></span>
                  <div><strong>Weekly digest</strong><span>Every Friday at 09:00</span></div>
                </div>
                <div class="bg-digest-recipient">
                  <span>Recipients</span>
                  <strong>Design team <span class="bg-digest-count">6</span></strong>
                </div>
                <div class="bg-digest-footer">
                  <span><i /> Scheduled</span>
                  <span class="bg-digest-button">Preview<Icon name="chevron-right" :size="13" /></span>
                </div>
              </div>
            </div>
          </Stage>
        </div>
        <h2>{{ study.title }}</h2>
        <p>{{ study.note }}</p>
      </article>
    </div>
  </div>
</template>
