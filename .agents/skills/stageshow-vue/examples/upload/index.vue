<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { ChevronLeft, ChevronRight, File, Folder, LayoutGrid, List, Search, Share } from 'lucide-vue-next'
import { Bar, Collapse, Count, Stage, States, Window, Meter, type Act, type Layout, type Point } from '../../kit'
import './upload.css'

// A file storage app, list view. A PDF sits on the desktop beside the
// Projects window. The user drags it in: the drag image rides with the arrow,
// the list lights up under it, and on the drop an upload row opens at the top
// (newest first). Its bar fills while the size counts up, then the row settles
// into an ordinary file row: Just now, 4.2 MB. Cmd+Z takes the upload back,
// which is exactly where the loop began.
//
// The upload is the story, so it gets the room: no sidebar, rows at reading
// size, and a list short enough that the new row is a tenth of the window, not
// a sliver at the top of a long one. Everything else is placeholder bars. The
// desktop strip holds the file at the start and the keycaps at the end.

type Ghost = { on: boolean; dropped: boolean; off: Point; at: Point }
type S = { up: boolean; mb: number; done: boolean; ghost: Ghost }

const initial: S = { up: false, mb: 0, done: false, ghost: { on: false, dropped: false, off: { x: 0, y: 0 }, at: { x: 0, y: 0 } } }

const FILE = 'Launch deck.pdf'
const MB = 4.2

type Geo = {
  win: { x: number; y: number; w: number; h: number }
  rows: number
  cols: string
  desk: { x: number; y: number }
}

// Wide: one gutter (40) above the window and left of the file; the window
// runs off the right and bottom, its Size column still whole in the crop.
// Compact: the file sits above the window, which runs off the bottom only
// with equal side gutters, so all three columns stay whole.
const GEO: Record<Layout, Geo> = {
  wide: { win: { x: 184, y: 40, w: 620, h: 420 }, rows: 9, cols: 'minmax(0, 1fr) 132px 118px', desk: { x: 40, y: 124 } },
  compact: { win: { x: 24, y: 120, w: 352, h: 300 }, rows: 6, cols: 'minmax(0, 1fr) 92px 76px', desk: { x: 20, y: 18 } },
}

type Kind = 'folder' | 'doc'
const ROWS: { kind: Kind; name: number; date: number; size: number }[] = [
  { kind: 'folder', name: 96, date: 84, size: 16 },
  { kind: 'doc', name: 132, date: 76, size: 40 },
  { kind: 'doc', name: 104, date: 88, size: 34 },
  { kind: 'folder', name: 80, date: 80, size: 16 },
  { kind: 'doc', name: 120, date: 72, size: 44 },
  { kind: 'doc', name: 92, date: 86, size: 36 },
  { kind: 'folder', name: 112, date: 78, size: 16 },
  { kind: 'doc', name: 100, date: 74, size: 38 },
  { kind: 'doc', name: 126, date: 82, size: 42 },
]

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
  overEl = null
})

async function script(a: Act<S>) {
  await a.wait(600)

  // 1. Pick the PDF up off the desktop by its icon
  a.mark('grab')
  const icon = a.rect('desk-icon')
  const file = a.rect('desk-file')
  const grab = { x: icon.x + icon.width / 2, y: icon.y + icon.height * 0.55 }
  await a.move(grab)
  await a.wait(240)
  const off = { x: grab.x - file.x, y: grab.y - file.y }

  // 2. Carry it into the window; the list lights up under it
  a.mark('drag')
  const list = a.rect('drop')
  await a.drag(
    { x: list.x + list.width * 0.36, y: list.y + list.height * 0.32 },
    (at) => {
      const ghost: Ghost = { on: true, dropped: false, off, at }
      a.put({ ghost })
      updateDropHover(ghost)
    },
    { duration: 1300, cursor: 'preserve' },
  )

  // 3. Drop: the upload row opens at the top, its bar fills and the size
  //    counts up with it
  a.mark('drop')
  await a.set((s) => {
    const ghost = { ...s.ghost, dropped: true }
    updateDropHover(ghost)
    return { up: true, ghost }
  })
  await a.wait(500)
  for (const [mb, ms] of [
    [1.1, 650],
    [2.3, 650],
    [3.4, 650],
    [MB, 600],
  ] as const) {
    await a.set({ mb })
    await a.wait(ms)
  }

  // 4. Uploaded: the bar gives way to Just now and the tint fades
  a.mark('done')
  await a.set({ done: true })
  await a.wait(2400)

  // 5. Cmd+Z takes the upload back; the row closes: back to the start
  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ up: false, ghost: initial.ghost })
  updateDropHover(initial.ghost)
  await a.wait(600)
  await a.snap({ mb: 0, done: false })
  await a.wait(300)
}

const fmtMb = (n: number) => n.toFixed(1)
</script>

<template>
  <Stage
    :width="760"
    :height="420"
    :compact="{ below: 560, width: 400, height: 340 }"
    :initial="initial"
    :script="script"
    accent="#0a6de6"
    :keys="{ wide: 'bottom-left', compact: 'top' }"
    :cursor="{ at: { at: 'drop', x: 0.36, y: 0.32 } }"
    class="up"
    v-slot="{ state: s, layout }"
  >
    <div
      class="up-desk"
      data-target="desk-file"
      :data-lifted="(s.ghost.on && !s.ghost.dropped) || undefined"
      :style="{ left: `${GEO[layout].desk.x}px`, top: `${GEO[layout].desk.y}px` }"
    >
      <span data-target="desk-icon">
        <span class="up-pdf">
          <span class="up-pdf__band">PDF</span>
        </span>
      </span>
      <span class="up-desk__name">{{ FILE }}</span>
    </div>

    <Window
      class="up-window"
      :style="{
        left: `${GEO[layout].win.x}px`,
        top: `${GEO[layout].win.y}px`,
        width: `${GEO[layout].win.w}px`,
        height: `${GEO[layout].win.h}px`,
      }"
      :body="{ className: 'up-body', 'data-crop': true }"
    >
      <template #lead>
        <span class="up-lead">
          <span class="up-nav">
            <ChevronLeft :size="18" :stroke-width="1.75" />
            <ChevronRight :size="18" :stroke-width="1.75" class="up-nav-off" />
          </span>
          <span class="up-heading">Projects</span>
        </span>
      </template>
      <template #toolbar>
        <span class="up-tools">
          <span class="up-views">
            <span class="up-view">
              <LayoutGrid :size="15" :stroke-width="1.75" />
            </span>
            <span class="up-view" data-on>
              <List :size="16" :stroke-width="1.75" />
            </span>
          </span>
          <Share :size="16" :stroke-width="1.75" />
          <Search :size="16" :stroke-width="1.75" />
        </span>
      </template>

      <div class="up-list" :data-compact="layout === 'compact' || undefined" :style="{ ['--cols' as string]: GEO[layout].cols }">
        <div class="up-head">
          <span>Name</span>
          <span>{{ layout === 'wide' ? 'Date Modified' : 'Modified' }}</span>
          <span>Size</span>
        </div>
        <div class="up-rows" data-target="drop" data-drop>
          <Collapse :open="s.up">
            <div class="up-row up-new" :data-done="s.done || undefined">
              <span class="up-name">
                <span class="up-pdf" data-small="true">
                  <span class="up-pdf__band" />
                </span>
                <span class="up-name__text">{{ FILE }}</span>
              </span>
              <States :value="s.done ? 'done' : 'up'" align="start">
                <template #up>
                  <Meter class="up-track" :value="s.mb / MB" />
                </template>
                <template #done>
                  <span>Just now</span>
                </template>
              </States>
              <span class="up-size">
                <Count :value="s.mb" :duration="600" :format="fmtMb" />
                {{ ' MB' }}
              </span>
            </div>
          </Collapse>
          <div v-for="(r, i) in ROWS.slice(0, GEO[layout].rows)" :key="i" class="up-row">
            <span class="up-name">
              <Folder v-if="r.kind === 'folder'" :size="18" :stroke-width="1.25" class="up-folder" />
              <File v-else :size="18" :stroke-width="1.25" class="up-doc" />
              <Bar :w="Math.round(r.name * (layout === 'wide' ? 1 : 0.75))" :h="7" :tone="3" />
            </span>
            <Bar :w="Math.round(r.date * (layout === 'wide' ? 1 : 0.75))" :h="7" :tone="2" />
            <Bar v-if="r.kind === 'folder'" :w="r.size" :h="2" :tone="3" />
            <Bar v-else :w="r.size" :h="7" :tone="2" />
          </div>
        </div>
      </div>
    </Window>

    <div
      ref="dragRef"
      class="up-drag"
      :data-show="(s.ghost.on && !s.ghost.dropped) || undefined"
      :data-dropped="s.ghost.dropped || undefined"
      :style="{ transform: `translate(${s.ghost.at.x - s.ghost.off.x}px, ${s.ghost.at.y - s.ghost.off.y}px)` }"
      aria-hidden="true"
    >
      <div class="up-drag__inner" :style="{ transformOrigin: `${s.ghost.off.x}px ${s.ghost.off.y}px` }">
        <span class="up-pdf">
          <span class="up-pdf__band">PDF</span>
        </span>
        <span class="up-drag__name">{{ FILE }}</span>
      </div>
    </div>
  </Stage>
</template>
