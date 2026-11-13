<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import {
  AppWindow,
  ChevronLeft,
  ChevronRight,
  Clock,
  Cloud,
  Download,
  File,
  FileText,
  Folder,
  HardDrive,
  LayoutGrid,
  List,
  Maximize2,
  Monitor,
  Search,
  Share,
  X,
} from 'lucide-vue-next'
import { Bar, Collapse, Stage, Text, Window, type Act, type Layout, type Point, type Rect } from '../../kit'
import './finder.css'

// Finder, list view. The user selects a photo, presses Space and Quick Look
// zooms out of its thumbnail; Space again and it zooms back. Then they drag the
// file onto Wallpapers in the sidebar: the drag image rides with the arrow (as
// macOS draws it, no grabbing hand), Wallpapers lights up under it, the row
// leaves the list. Cmd+Z puts it back and a click in the empty list clears the
// selection, which is exactly where the loop began.
//
// Icons: Finder has no web icon pack, so lucide is used deliberately for its
// SF Symbols-like outline sidebar glyphs (one family, one stroke).

type Ghost = { on: boolean; dropped: boolean; off: Point; at: Point }
type S = { sel: boolean; ql: boolean; moved: boolean; ghost: Ghost }

const initial: S = { sel: false, ql: false, moved: false, ghost: { on: false, dropped: false, off: { x: 0, y: 0 }, at: { x: 0, y: 0 } } }

const FILE = 'Fuji.jpg'
const DROP = 'Wallpapers'

type Geo = {
  win: { x: number; y: number; w: number; h: number }
  side: number
  rows: number
  cols: string
  ql: { x: number; y: number; w: number }
}

const GEO: Record<Layout, Geo> = {
  wide: { win: { x: 40, y: 40, w: 880, h: 500 }, side: 180, rows: 10, cols: 'minmax(0, 1fr) 150px 76px 120px', ql: { x: 350, y: 66, w: 380 } },
  compact: { win: { x: 24, y: 24, w: 520, h: 420 }, side: 150, rows: 8, cols: '196px 140px 70px 110px', ql: { x: 68, y: 72, w: 264 } },
}

const QL_BAR = 38
const qlHeight = (w: number) => QL_BAR + Math.round((w * 3) / 4)

// The list: what each row is, and how long its placeholder name runs.
type Kind = 'folder' | 'doc' | 'image' | 'hero'
const ROWS: { kind: Kind; name: number; date: number; size: number; type: number }[] = [
  { kind: 'folder', name: 92, date: 88, size: 14, type: 40 },
  { kind: 'doc', name: 124, date: 80, size: 34, type: 72 },
  { kind: 'folder', name: 70, date: 92, size: 14, type: 40 },
  { kind: 'hero', name: 0, date: 84, size: 38, type: 64 },
  { kind: 'image', name: 108, date: 76, size: 36, type: 64 },
  { kind: 'doc', name: 86, date: 90, size: 30, type: 78 },
  { kind: 'folder', name: 116, date: 84, size: 14, type: 40 },
  { kind: 'doc', name: 98, date: 78, size: 40, type: 70 },
  { kind: 'image', name: 80, date: 88, size: 34, type: 64 },
  { kind: 'doc', name: 112, date: 82, size: 32, type: 74 },
]

// The same local photograph is shared by its thumbnail and Quick Look.
const PHOTO = new URL('../wikipedia/kawaguchiko.jpg', import.meta.url).href
const ALT_PHOTO = new URL('../wikipedia/fuji.jpg', import.meta.url).href

async function script(a: Act<S>) {
  await a.wait(500)

  // 1. Select the photo: click the row, clear of its name
  a.mark('select')
  const row = a.rect('row-hero')
  await a.click({ x: row.x + 176, y: row.y + row.height * 0.6 })
  await a.set({ sel: true })
  await a.wait(650)

  // 2. Space: Quick Look zooms out of the thumbnail
  a.mark('open')
  await a.key('space')
  await a.set({ ql: true })
  await a.wait(2400)

  // 3. Space again: it zooms back into the row
  a.mark('close')
  await a.key('space')
  await a.set({ ql: false })
  await a.wait(700)

  // 4. Drag the file by its icon onto Wallpapers in the sidebar
  a.mark('drag')
  const icon = a.rect('hero-drag')
  const thumb = a.rect('thumb')
  const grab = { x: thumb.x + thumb.width / 2, y: thumb.y + thumb.height / 2 + 1 }
  await a.move(grab)
  await a.wait(220)
  const line = a.rect('row-hero')
  const off = { x: grab.x - icon.x, y: grab.y - line.y }
  // Finder keeps its arrow. Pickup and each carried position belong to the
  // drag callback, so the image and cursor are painted together after press.
  // Drop just past the folder's name, so the drag image never hides it.
  const drop = a.rect('side-drop')
  await a.drag({ x: drop.x + 114, y: drop.y + drop.height * 0.55 }, (at) => {
    a.put({ ghost: { on: true, dropped: false, off, at } })
  }, { duration: 1150, cursor: 'preserve' })
  a.mark('drop')
  await a.set((s) => ({ moved: true, ghost: { ...s.ghost, dropped: true } }))
  await a.wait(1900)

  // 5. Cmd+Z: the move is undone and the file comes back, still selected
  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ moved: false, ghost: initial.ghost })
  await a.wait(1100)

  // 6. A click in the empty list clears the selection: back to the start
  await a.click({ at: 'blank', x: 0.56, y: 0.5 })
  await a.set({ sel: false })
  await a.wait(900)
}

function qlInfo(s: S, rect: (n: string) => Rect, layout: Layout) {
  const g = GEO[layout]
  const qh = qlHeight(g.ql.w)
  const t = rect('thumb')
  const k = t.width ? t.width / g.ql.w : 0.05
  const box = s.ql
    ? { left: `${g.ql.x}px`, top: `${g.ql.y}px`, width: `${g.ql.w}px`, height: `${qh}px`, borderRadius: '12px' }
    : { left: `${t.x}px`, top: `${t.y + t.height / 2 - (qh * k) / 2}px`, width: `${g.ql.w * k}px`, height: `${qh * k}px`, borderRadius: `${12 * k}px` }
  const barHeight = `${s.ql ? 38 : 38 * k}px`
  return { g, box, barHeight }
}

const dragRef = ref<HTMLDivElement | null>(null)
let overEl: HTMLElement | null = null

function updateDropHover(ghost: Ghost) {
  const following = ghost.on && !ghost.dropped
  const { x, y } = ghost.at
  const root = dragRef.value?.closest<HTMLElement>('.ss-stage')
  let next: HTMLElement | null = null
  if (following && root) {
    const box = root.getBoundingClientRect()
    const scale = box.width / root.offsetWidth || 1
    const hit = document.elementFromPoint(box.left + x * scale, box.top + y * scale)?.closest<HTMLElement>('[data-drop]') ?? null
    if (hit && root.contains(hit)) next = hit
  }
  if (next !== overEl) {
    overEl?.removeAttribute('data-over')
    next?.setAttribute('data-over', '')
    overEl = next
  }
}

onBeforeUnmount(() => {
  overEl?.removeAttribute('data-over')
})
</script>

<template>
  <Stage
    :width="820"
    :height="420"
    :compact="{ below: 560, width: 400, height: 340 }"
    :initial="initial"
    :script="script"
    accent="#0a6de6"
    :cursor="{ at: { at: 'blank', x: 0.56, y: 0.5 } }"
    class="fq"
    v-slot="{ state: s, rect, layout }"
  >
    <template v-for="info in [qlInfo(s, rect, layout)]" :key="layout">
      <Window
        class="fq-window"
        :style="{ left: `${info.g.win.x}px`, top: `${info.g.win.y}px`, width: `${info.g.win.w}px`, height: `${info.g.win.h}px` }"
        :sidebar-width="info.g.side"
        :body="{ className: 'fq-body', 'data-crop': true }"
      >
        <template #sidebar>
          <div class="fq-side">
            <Bar :w="44" :h="5" :tone="3" class="fq-side__label" />
            <div class="fq-side__item">
              <span class="fq-side__icon"><Clock :size="15" :stroke-width="1.6" /></span>
              <Bar :w="46" :h="6" :tone="3" />
            </div>
            <div class="fq-side__item">
              <span class="fq-side__icon"><AppWindow :size="15" :stroke-width="1.6" /></span>
              <Bar :w="64" :h="6" :tone="3" />
            </div>
            <div class="fq-side__item">
              <span class="fq-side__icon"><Monitor :size="15" :stroke-width="1.6" /></span>
              <Bar :w="42" :h="6" :tone="3" />
            </div>
            <div class="fq-side__item">
              <span class="fq-side__icon"><FileText :size="15" :stroke-width="1.6" /></span>
              <Bar :w="58" :h="6" :tone="3" />
            </div>
            <div class="fq-side__item" data-current="true">
              <span class="fq-side__icon"><Download :size="15" :stroke-width="1.6" /></span>
              <Text>Downloads</Text>
            </div>
            <div class="fq-side__item" data-target="side-drop" data-drop="true">
              <span class="fq-side__icon"><Folder :size="15" :stroke-width="1.6" /></span>
              <Text>{{ DROP }}</Text>
            </div>
            <Bar :w="52" :h="5" :tone="3" class="fq-side__label" />
            <div class="fq-side__item">
              <span class="fq-side__icon"><Cloud :size="15" :stroke-width="1.6" /></span>
              <Bar :w="56" :h="6" :tone="3" />
            </div>
            <div class="fq-side__item">
              <span class="fq-side__icon"><HardDrive :size="15" :stroke-width="1.6" /></span>
              <Bar :w="70" :h="6" :tone="3" />
            </div>
          </div>
        </template>

        <template #lead>
          <span class="fq-lead">
            <span class="fq-nav">
              <ChevronLeft :size="17" :stroke-width="1.75" />
              <ChevronRight :size="17" :stroke-width="1.75" class="fq-nav-off" />
            </span>
            <span class="fq-heading">Downloads</span>
          </span>
        </template>

        <template #toolbar>
          <span class="fq-tools">
            <span class="fq-views">
              <span class="fq-view">
                <LayoutGrid :size="14" :stroke-width="1.75" />
              </span>
              <span class="fq-view" data-on>
                <List :size="15" :stroke-width="1.75" />
              </span>
            </span>
            <Share :size="15" :stroke-width="1.75" />
            <Search :size="15" :stroke-width="1.75" />
          </span>
        </template>

        <div class="fq-list" :style="{ ['--cols' as string]: info.g.cols }">
          <div class="fq-head">
            <span>Name</span>
            <span>Date Modified</span>
            <span>Size</span>
            <span>Kind</span>
          </div>
          <div class="fq-rows">
            <!-- Stripes belong to positions, not to rows, as in AppKit:
                 a row that leaves slides the rest up over them -->
            <div class="fq-stripes" aria-hidden="true">
              <span v-for="i in info.g.rows + 4" :key="i" />
            </div>
            <template v-for="(r, i) in ROWS.slice(0, info.g.rows)" :key="i">
              <Collapse v-if="r.kind === 'hero'" :open="!s.moved">
                <div class="fq-row" :data-sel="s.sel || undefined" data-target="row-hero">
                  <span class="fq-name">
                    <span class="fq-name__drag" data-target="hero-drag">
                      <span class="fq-thumb" data-target="thumb">
                        <img class="fq-photo" :src="PHOTO" alt="" :draggable="false" />
                      </span>
                      <span class="fq-name__text">{{ FILE }}</span>
                    </span>
                  </span>
                  <Bar :w="r.date" :h="6" :tone="2" />
                  <Bar :w="r.size" :h="6" :tone="2" />
                  <Bar :w="r.type" :h="6" :tone="2" />
                </div>
              </Collapse>
              <div v-else class="fq-row">
                <span class="fq-name">
                  <span class="fq-name__drag">
                    <Folder v-if="r.kind === 'folder'" :size="16" :stroke-width="1.25" class="fq-folder" />
                    <File v-else-if="r.kind === 'doc'" :size="16" :stroke-width="1.25" class="fq-doc" />
                    <span v-else class="fq-thumb">
                      <img class="fq-photo" :src="ALT_PHOTO" alt="" :draggable="false" />
                    </span>
                    <Bar :w="r.name" :h="6" :tone="3" />
                  </span>
                </span>
                <Bar :w="r.date" :h="6" :tone="2" />
                <Bar v-if="r.kind === 'folder'" :w="r.size" :h="2" :tone="3" />
                <Bar v-else :w="r.size" :h="6" :tone="2" />
                <Bar :w="r.type" :h="6" :tone="2" />
              </div>
            </template>
            <div class="fq-blank" data-target="blank" />
          </div>
        </div>
      </Window>

      <div
        class="fq-ql"
        :data-open="s.ql || undefined"
        :style="info.box"
      >
        <div class="fq-ql__bar" :style="{ height: info.barHeight }">
          <span class="fq-ql__btns">
            <X :size="14" :stroke-width="1.75" />
            <Maximize2 :size="12" :stroke-width="1.75" />
          </span>
          <span class="fq-ql__title">{{ FILE }}</span>
          <span class="fq-ql__right">
            <span v-if="layout === 'wide'" class="fq-ql__open">Open with Preview</span>
            <Share :size="14" :stroke-width="1.75" />
          </span>
        </div>
        <img class="fq-photo fq-ql__photo" :src="PHOTO" alt="" :draggable="false" />
      </div>

      <div
        ref="dragRef"
        :data-drop-check="updateDropHover(s.ghost)"
        class="fq-drag"
        :data-show="(s.ghost.on && !s.ghost.dropped) || undefined"
        :data-dropped="s.ghost.dropped || undefined"
        :style="{ transform: `translate(${s.ghost.at.x - s.ghost.off.x}px, ${s.ghost.at.y - s.ghost.off.y}px)` }"
        aria-hidden="true"
      >
        <div class="fq-drag__inner" :style="{ transformOrigin: `${s.ghost.off.x}px ${s.ghost.off.y}px` }">
          <span class="fq-thumb">
            <img class="fq-photo" :src="PHOTO" alt="" :draggable="false" />
          </span>
          <span class="fq-drag__name">{{ FILE }}</span>
        </div>
      </div>
    </template>
  </Stage>
</template>
