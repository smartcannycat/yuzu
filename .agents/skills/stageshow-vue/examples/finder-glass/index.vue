<script setup lang="ts">
import {
  AppWindow,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  CircleArrowDown,
  Clock,
  Cloud,
  Columns3,
  Ellipsis,
  File,
  FileText,
  Folder,
  House,
  LayoutGrid,
  Maximize2,
  Monitor,
  Plus,
  Search,
  Share,
  Tag,
  Users,
  X,
} from 'lucide-vue-next'
import { Bar, Stage, Text, Window, type Act, type Layout, type Rect, States } from '../../kit'
import './finder-glass.css'

// Finder in the Liquid Glass design (macOS Tahoe, 26), in column view, drawn
// from a real macOS 26 screenshot: a floating rounded sidebar panel inset in
// the window that holds the larger traffic lights, a toolbar with no bar of
// its own (separate glass buttons, each with its label under it, the icon and
// text mode), the path bar as one rounded capsule with a round + beside it,
// and columns split by hairlines.
//
// The story: in films, a click on japan slides its column in and the title
// follows; a click picks a photo in it; Space opens Quick Look out of its
// thumbnail and Space again zooms it back; a click on films in the first
// column closes the japan column, which is exactly where the loop began.
//
// Icons: Finder has no web icon pack, so lucide is used deliberately for its
// SF Symbols-like outlines (one family, one stroke).

type S = { lis: boolean; file: boolean; ql: boolean }

const initial: S = { lis: false, file: false, ql: false }

const FILE = 'Fuji.jpg'

type Geo = {
  win: { x: number; y: number; w: number; h: number }
  side: number
  /** The folders shown as columns, left to right: films, japan and before them, in wide, Documents */
  docs: boolean
  ql: { x: number; y: number; w: number }
}

const GEO: Record<Layout, Geo> = {
  wide: { win: { x: 40, y: 40, w: 780, h: 480 }, side: 196, docs: true, ql: { x: 328, y: 142, w: 270 } },
  compact: { win: { x: 20, y: 20, w: 460, h: 400 }, side: 132, docs: false, ql: { x: 20, y: 108, w: 232 } },
}

const QL_BAR = 38
const qlHeight = (w: number) => QL_BAR + Math.round((w * 3) / 4)

// Column rows: what each row is, and how long its placeholder name runs
type Kind = 'folder' | 'doc' | 'image'
type Row = { kind: Kind; name: number | string; target?: string }

const DOCUMENTS: Row[] = [
  { kind: 'folder', name: 74 },
  { kind: 'folder', name: 96 },
  { kind: 'folder', name: 'films', target: 'films' },
  { kind: 'folder', name: 62 },
  { kind: 'doc', name: 104 },
  { kind: 'doc', name: 82 },
  { kind: 'doc', name: 92 },
]

const FILMS: Row[] = [
  { kind: 'folder', name: 58 },
  { kind: 'folder', name: 'japan', target: 'japan' },
  { kind: 'folder', name: 72 },
  { kind: 'doc', name: 96 },
  { kind: 'doc', name: 80 },
  { kind: 'doc', name: 88 },
]

const LISBON: Row[] = [
  { kind: 'image', name: 70 },
  { kind: 'image', name: 88 },
  { kind: 'image', name: FILE, target: 'file' },
  { kind: 'image', name: 64 },
  { kind: 'image', name: 80 },
]

// The same local photograph is shared by its thumbnail and Quick Look.
const PHOTO = new URL('../wikipedia/kawaguchiko.jpg', import.meta.url).href
const ALT_PHOTO = new URL('../wikipedia/fuji.jpg', import.meta.url).href

const SIDEBAR_ITEMS: { icon: any; label: string; section?: string; current?: boolean; cloud?: boolean }[] = [
  { icon: Clock, label: 'Recents' },
  { icon: Users, label: 'Shared' },
  { icon: AppWindow, label: 'Applications', section: 'Favorites' },
  { icon: Folder, label: 'Studio' },
  { icon: CircleArrowDown, label: 'Downloads' },
  { icon: Monitor, label: 'Desktop', cloud: true },
  { icon: FileText, label: 'Documents', current: true, cloud: true },
  { icon: Cloud, label: 'iCloud Drive', section: 'Locations' },
  { icon: House, label: 'mayachen' },
]

async function script(a: Act<S>) {
  await a.wait(700)

  // 1. Open japan: its column slides in and the title follows
  a.mark('folder')
  await a.click({ at: 'japan', x: 0.62, y: 0.6 })
  await a.set({ lis: true })
  await a.wait(900)

  // 2. Pick the photo in it
  a.mark('file')
  await a.click({ at: 'file', x: 0.66, y: 0.6 })
  await a.set({ file: true })
  await a.wait(600)

  // 3. Space: Quick Look zooms out of the thumbnail
  a.mark('open')
  await a.key('space')
  await a.set({ ql: true })
  await a.wait(2400)

  // 4. Space again: it zooms back into the row
  a.mark('close')
  await a.key('space')
  await a.set({ ql: false })
  await a.wait(800)

  // 5. Back to films: the japan column closes, as at the start
  a.mark('back')
  // (compact has no first column: Back does it, aimed at the back half)
  await a.click(a.layout === 'wide' ? { at: 'films', x: 0.66, y: 0.6 } : { at: 'back', x: 0.4, y: 0.56 })
  await a.set({ lis: false, file: false })
  await a.wait(1400)
}

function qlInfo(s: S, rect: (n: string) => Rect, layout: Layout) {
  const g = GEO[layout]
  const wide = layout === 'wide'
  const qh = qlHeight(g.ql.w)
  const t = rect('thumb')
  const k = t.width ? t.width / g.ql.w : 0.05
  const box = s.ql
    ? { left: `${g.ql.x}px`, top: `${g.ql.y}px`, width: `${g.ql.w}px`, height: `${qh}px`, borderRadius: '18px' }
    : { left: `${t.x}px`, top: `${t.y + t.height / 2 - (qh * k) / 2}px`, width: `${g.ql.w * k}px`, height: `${qh * k}px`, borderRadius: `${18 * k}px` }
  const barHeight = `${s.ql ? QL_BAR : QL_BAR * k}px`
  return { g, wide, box, barHeight }
}
</script>

<template>
  <Stage
    :width="860"
    :height="440"
    :compact="{ below: 560, width: 400, height: 340 }"
    :initial="initial"
    :script="script"
    accent="#0a6de6"
    greys="cool"
    :cursor="{ at: { wide: { at: 'films', x: 0.66, y: 0.6 }, compact: { at: 'back', x: 0.4, y: 0.56 } } }"
    class="fgl"
    v-slot="{ state: s, rect, layout }"
  >
    <template v-for="info in [qlInfo(s, rect, layout)]" :key="layout">
      <Window
        class="fgl-window"
        :style="{ left: `${info.g.win.x}px`, top: `${info.g.win.y}px`, width: `${info.g.win.w}px`, height: `${info.g.win.h}px` }"
        :sidebar-width="info.g.side"
        sidebar-style="floating"
        lights-size="large"
        bar-size="tall"
        :body="{ className: 'fgl-body', 'data-crop': true }"
      >
        <template #sidebar>
          <div class="fgl-side">
            <template v-for="(item, idx) in SIDEBAR_ITEMS" :key="idx">
              <Text v-if="item.section" class="fgl-side__label">{{ item.section }}</Text>
              <div class="fgl-side__item" :data-current="item.current || undefined">
                <span class="fgl-side__icon">
                  <component :is="item.icon" :size="16" :stroke-width="1.6" />
                </span>
                <Text>{{ item.label }}</Text>
                <Cloud v-if="item.cloud" :size="13" :stroke-width="1.6" class="fgl-side__cloud" />
              </div>
            </template>
          </div>
        </template>

        <template #lead>
          <span class="fgl-lead">
            <span class="fgl-tool">
              <span class="fgl-cap fgl-nav" :data-target="info.wide ? undefined : 'back'">
                <ChevronLeft :size="16" :stroke-width="1.6" />
                <span class="fgl-nav__rule" />
                <ChevronRight :size="16" :stroke-width="1.6" class="fgl-off" />
              </span>
              <span class="fgl-tool__label">Back/Forward</span>
            </span>
            <span class="fgl-heading">
              <States class="fgl-names" :value="s.lis ? 'japan' : 'films'" align="start" :states="{ films: 'films', japan: 'japan' }" />
            </span>
          </span>
        </template>

        <template v-if="info.wide" #toolbar>
          <span class="fgl-tools">
            <span class="fgl-tool">
              <span class="fgl-cap">
                <Columns3 :size="16" :stroke-width="1.6" />
                <ChevronsUpDown :size="11" :stroke-width="2" />
              </span>
              <span class="fgl-tool__label">View</span>
            </span>
            <span class="fgl-tool">
              <span class="fgl-cap">
                <LayoutGrid :size="16" :stroke-width="1.6" />
                <ChevronDown :size="11" :stroke-width="2" />
              </span>
              <span class="fgl-tool__label">Group</span>
            </span>
            <span class="fgl-tool">
              <span class="fgl-round">
                <Ellipsis :size="16" :stroke-width="1.6" />
              </span>
              <span class="fgl-tool__label">Action</span>
            </span>
            <span class="fgl-tool">
              <span class="fgl-round">
                <Share :size="16" :stroke-width="1.6" />
              </span>
              <span class="fgl-tool__label">Share</span>
            </span>
            <span class="fgl-tool">
              <span class="fgl-round">
                <Tag :size="16" :stroke-width="1.6" />
              </span>
              <span class="fgl-tool__label">Add Tags</span>
            </span>
            <span class="fgl-tool">
              <span class="fgl-round">
                <Search :size="16" :stroke-width="1.6" />
              </span>
              <span class="fgl-tool__label">Search</span>
            </span>
          </span>
        </template>

        <div class="fgl-path">
          <span class="fgl-path__tab">
            <States class="fgl-names" :value="s.lis ? 'japan' : 'films'" align="center" :states="{ films: 'films', japan: 'japan' }" />
          </span>
          <span class="fgl-path__add">
            <Plus :size="14" :stroke-width="1.75" />
          </span>
        </div>

        <div class="fgl-cols" :data-docs="info.g.docs || undefined">
          <div v-if="info.g.docs" class="fgl-col" data-open="true">
            <div
              v-for="(r, i) in DOCUMENTS"
              :key="i"
              class="fgl-row"
              :data-sel="r.target === 'films' ? (s.lis ? 'quiet' : 'focus') : undefined"
              :data-target="r.target"
            >
              <Folder v-if="r.kind === 'folder'" :size="15" :stroke-width="1.25" class="fgl-folder" />
              <File v-else-if="r.kind === 'doc'" :size="15" :stroke-width="1.25" class="fgl-doc" />
              <span v-else class="fgl-thumb" :data-target="r.target === 'file' ? 'thumb' : undefined">
                <img class="fgl-photo" :src="r.target === 'file' ? PHOTO : ALT_PHOTO" alt="" :draggable="false" />
              </span>
              <span v-if="typeof r.name === 'string'" class="fgl-row__name">{{ r.name }}</span>
              <Bar v-else :w="r.name" :h="6" :tone="3" />
              <ChevronRight v-if="r.kind === 'folder'" :size="12" :stroke-width="2" class="fgl-row__chev" />
            </div>
          </div>

          <div class="fgl-col" data-open="true">
            <div
              v-for="(r, i) in FILMS"
              :key="i"
              class="fgl-row"
              :data-sel="r.target === 'japan' ? (s.lis ? (s.file ? 'quiet' : 'focus') : undefined) : undefined"
              :data-target="r.target"
            >
              <Folder v-if="r.kind === 'folder'" :size="15" :stroke-width="1.25" class="fgl-folder" />
              <File v-else-if="r.kind === 'doc'" :size="15" :stroke-width="1.25" class="fgl-doc" />
              <span v-else class="fgl-thumb" :data-target="r.target === 'file' ? 'thumb' : undefined">
                <img class="fgl-photo" :src="r.target === 'file' ? PHOTO : ALT_PHOTO" alt="" :draggable="false" />
              </span>
              <span v-if="typeof r.name === 'string'" class="fgl-row__name">{{ r.name }}</span>
              <Bar v-else :w="r.name" :h="6" :tone="3" />
              <ChevronRight v-if="r.kind === 'folder'" :size="12" :stroke-width="2" class="fgl-row__chev" />
            </div>
          </div>

          <div class="fgl-col" :data-open="s.lis || undefined">
            <div
              v-for="(r, i) in LISBON"
              :key="i"
              class="fgl-row"
              :data-sel="r.target === 'file' ? (s.file ? 'focus' : undefined) : undefined"
              :data-target="r.target"
            >
              <Folder v-if="r.kind === 'folder'" :size="15" :stroke-width="1.25" class="fgl-folder" />
              <File v-else-if="r.kind === 'doc'" :size="15" :stroke-width="1.25" class="fgl-doc" />
              <span v-else class="fgl-thumb" :data-target="r.target === 'file' ? 'thumb' : undefined">
                <img class="fgl-photo" :src="r.target === 'file' ? PHOTO : ALT_PHOTO" alt="" :draggable="false" />
              </span>
              <span v-if="typeof r.name === 'string'" class="fgl-row__name">{{ r.name }}</span>
              <Bar v-else :w="r.name" :h="6" :tone="3" />
              <ChevronRight v-if="r.kind === 'folder'" :size="12" :stroke-width="2" class="fgl-row__chev" />
            </div>
          </div>
        </div>
      </Window>

      <div class="fgl-ql" :data-open="s.ql || undefined" :style="info.box">
        <div class="fgl-ql__bar" :style="{ height: info.barHeight }">
          <span class="fgl-round fgl-ql__round">
            <X :size="14" :stroke-width="1.75" />
          </span>
          <span class="fgl-round fgl-ql__round">
            <Maximize2 :size="12" :stroke-width="1.75" />
          </span>
          <span class="fgl-ql__title">{{ FILE }}</span>
          <span v-if="info.g.ql.w >= 300" class="fgl-cap fgl-ql__open">Open with Preview</span>
          <span class="fgl-round fgl-ql__round">
            <Share :size="14" :stroke-width="1.75" />
          </span>
        </div>
        <img class="fgl-photo fgl-ql__photo" :src="PHOTO" alt="" :draggable="false" />
      </div>
    </template>
  </Stage>
</template>
