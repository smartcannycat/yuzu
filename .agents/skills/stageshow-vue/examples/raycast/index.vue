<script setup lang="ts">
import {
  AppWindow,
  ArrowLeft,
  BookOpen,
  Globe,
  Search,
  Calculator,
  Calendar,
  ChevronDown,
  ClipboardList,
  Folder,
  Image,
  Link,
  Music,
  Settings,
  Text as TextIcon,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import { Bar, Collapse, Stage, Text, type Act } from '../../kit'
import './raycast.css'

// Raycast over a blurred desktop. Type "clip", Clipboard History is the first
// result, Enter pushes the command, the list opens with its preview pane,
// Down moves to a copied color, Esc pops back to root search (the loop).

type S = { query: string; view: 'root' | 'clip'; sel: number }

const initial: S = { query: '', view: 'root', sel: 0 }

type Row = { id: string; icon: Component; tile: string; title: number; sub: number; acc: number }

// Root rows. Clipboard History is its own row; the rest are placeholders.
const ROWS: Row[] = [
  { id: 'r1', icon: Folder, tile: '#3d8bfd', title: 52, sub: 0, acc: 56 },
  { id: 'r2', icon: Calendar, tile: '#ff5f57', title: 64, sub: 40, acc: 50 },
  { id: 'r3', icon: Music, tile: '#fc3c64', title: 44, sub: 0, acc: 56 },
  { id: 'r4', icon: Settings, tile: '#8e8e93', title: 78, sub: 46, acc: 50 },
  { id: 'r5', icon: AppWindow, tile: '#5e5ce6', title: 58, sub: 0, acc: 56 },
  { id: 'r6', icon: Calculator, tile: '#ff9f0a', title: 70, sub: 0, acc: 50 },
  { id: 'r7', icon: Image, tile: '#30b0c7', title: 86, sub: 52, acc: 50 },
  { id: 'r8', icon: Folder, tile: '#3d8bfd', title: 66, sub: 0, acc: 56 },
]

// Which rows survive each query, in the order Raycast ranks them.
function shown(q: string): string[] {
  if (q === '') return ['r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7', 'r8']
  if (q === 'c') return ['ch', 'r2', 'r6', 'r3']
  if (q === 'cl') return ['ch', 'r6', 'r7']
  return ['ch', 'r7']
}

const FALLBACK = [
  { icon: Globe, tile: '#0a84ff', title: 92, acc: 50 },
  { icon: Search, tile: '#636366', title: 74, acc: 56 },
  { icon: BookOpen, tile: '#34c759', title: 60, acc: 50 },
]

type Entry = { kind: 'text' | 'color' | 'link' | 'image'; label?: string; w: number }
const ENTRIES: Entry[] = [
  { kind: 'text', label: 'Ship the new onboarding on Thursday', w: 0 },
  { kind: 'color', label: '#FF6363', w: 0 },
  { kind: 'link', w: 96 },
  { kind: 'text', w: 120 },
  { kind: 'image', w: 82 },
  { kind: 'text', w: 104 },
  { kind: 'link', w: 74 },
]

const INFO_ROWS = [
  [58, 46, 52],
  [70, 34, 28],
  [44, 60, 66],
  [62, 52, 40],
]

function entryIconComponent(kind: Entry['kind']): Component {
  return kind === 'link' ? Link : kind === 'image' ? Image : TextIcon
}

async function script(a: Act<S>) {
  await a.wait(1000)
  a.mark('type')
  await a.type('query', 'clip', { interval: 150 })
  await a.wait(900)
  a.mark('open')
  await a.key('enter')
  await a.set({ view: 'clip', sel: 0 })
  await a.wait(2200)
  a.mark('down')
  await a.key('down')
  await a.set({ sel: 1 })
  await a.wait(2400)
  a.mark('back')
  await a.key('esc')
  await a.set({ view: 'root', query: '', sel: 0 })
  await a.wait(1400)
}
</script>

<template>
  <Stage
    :width="760"
    :height="440"
    :compact="{ below: 560, width: 400, height: 380 }"
    :initial="initial"
    :script="script"
    theme="dark"
    keys="bottom"
    class="rc-stage"
    v-slot="{ state: s, layout }"
  >
    <div class="rc-desktop" :data-layout="layout">
      <div class="rc-wallpaper" />
      <div class="rc-menubar">
        <span class="rc-menubar-left">
          <Bar :w="34" :h="7" :tone="5" />
          <Bar :w="22" :h="6" :tone="4" />
          <Bar :w="26" :h="6" :tone="4" />
          <Bar :w="30" :h="6" :tone="4" />
        </span>
        <span class="rc-menubar-right">
          <Bar :w="14" :h="10" :r="3" :tone="4" />
          <Bar :w="14" :h="10" :r="3" :tone="4" />
          <Bar :w="14" :h="10" :r="3" :tone="4" />
          <Bar :w="58" :h="6" :tone="5" />
        </span>
      </div>
      <div class="rc-window">
        <!-- Root -->
        <div class="rc-page rc-root" :data-show="s.view === 'root' || undefined">
          <div class="rc-search">
            <span class="rc-input">
              <span v-if="s.query" class="rc-query">{{ s.query }}</span>
              <span :key="s.query" class="rc-caret" />
              <span class="rc-placeholder" :data-hidden="!!s.query || undefined">
                Search for apps and commands...
              </span>
            </span>
          </div>
          <div class="rc-list">
            <div class="rc-section">
              <span class="rc-heads">
                <Text class="rc-head" :data-show="!s.query || undefined">Suggestions</Text>
                <Text class="rc-head" :data-show="!!s.query || undefined">Results</Text>
              </span>
            </div>
            <Collapse class="rc-filter" :open="shown(s.query).includes('ch')">
              <div class="rc-row" :data-selected="shown(s.query)[0] === 'ch' || undefined">
                <span class="rc-tile" :style="{ background: '#ff6363' }">
                  <ClipboardList :size="13" :stroke-width="2.25" />
                </span>
                <Text class="rc-title">Clipboard History</Text>
                <Text class="rc-sub">Raycast</Text>
                <span class="rc-spacer" />
                <Text class="rc-acc">Command</Text>
              </div>
            </Collapse>
            <Collapse v-for="r in ROWS" :key="r.id" class="rc-filter" :open="shown(s.query).includes(r.id)">
              <div class="rc-row" :data-selected="shown(s.query)[0] === r.id || undefined">
                <span class="rc-tile" :style="{ background: r.tile }">
                  <component :is="r.icon" :size="13" :stroke-width="2.25" />
                </span>
                <Bar :w="r.title" :h="7" :tone="5" />
                <Bar v-if="r.sub > 0" :w="r.sub" :h="7" :tone="3" />
                <span class="rc-spacer" />
                <Bar :w="r.acc" :h="6" :tone="3" />
              </div>
            </Collapse>
            <Collapse class="rc-filter" :open="!!s.query">
              <div class="rc-section">
                <span class="rc-heads">
                  <Text class="rc-head" data-show>{{ `Use "${s.query || 'clip'}" with...` }}</Text>
                </span>
              </div>
              <div v-for="(f, i) in FALLBACK" :key="i" class="rc-row">
                <span class="rc-tile" :style="{ background: f.tile }">
                  <component :is="f.icon" :size="13" :stroke-width="2.25" />
                </span>
                <Bar :w="f.title" :h="7" :tone="5" />
                <span class="rc-spacer" />
                <Bar :w="f.acc" :h="6" :tone="3" />
              </div>
            </Collapse>
          </div>
        </div>

        <!-- Clip -->
        <div class="rc-page rc-clip" :data-show="s.view === 'clip' || undefined">
          <div class="rc-search">
            <span class="rc-back">
              <ArrowLeft :size="14" :stroke-width="2" />
            </span>
            <span class="rc-input">
              <span class="rc-caret" />
              <span class="rc-placeholder">Type to filter entries...</span>
            </span>
            <span class="rc-dropdown">
              <Text>All Types</Text>
              <ChevronDown :size="13" :stroke-width="2" />
            </span>
          </div>
          <div class="rc-split">
            <div class="rc-entries">
              <div class="rc-section">
                <Text>Today</Text>
              </div>
              <div v-for="(e, i) in ENTRIES" :key="i" class="rc-row rc-entry" :data-selected="s.sel === i || undefined">
                <span v-if="e.kind === 'color'" class="rc-swatch" />
                <component :is="entryIconComponent(e.kind)" v-else class="rc-entry-icon" :size="15" :stroke-width="1.75" />
                <Text v-if="e.label" class="rc-title rc-clamp">{{ e.label }}</Text>
                <Bar v-else :w="layout === 'compact' ? Math.round(e.w * 0.7) : e.w" :h="7" :tone="4" />
              </div>
            </div>
            <div class="rc-preview">
              <div class="rc-preview-top">
                <div class="rc-layer" :data-show="s.sel === 0 || undefined">
                  <Text class="rc-preview-text" wrap>
                    Ship the new onboarding on Thursday
                  </Text>
                </div>
                <div class="rc-layer rc-layer-color" :data-show="s.sel === 1 || undefined">
                  <span class="rc-big-swatch" />
                  <Text class="rc-preview-text">#FF6363</Text>
                </div>
              </div>
              <div class="rc-info">
                <Text class="rc-info-head">Information</Text>
                <div v-for="([l, v0, v1], i) in INFO_ROWS" :key="i" class="rc-info-row">
                  <Bar :w="l" :h="6" :tone="3" />
                  <span class="rc-info-val">
                    <Bar class="rc-v" :data-show="s.sel === 0 || undefined" :w="v0" :h="6" :tone="4" />
                    <Bar class="rc-v" :data-show="s.sel === 1 || undefined" :w="v1" :h="6" :tone="4" />
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rc-actions">
          <span class="rc-mark" />
          <span class="rc-spacer" />
          <Bar :w="78" :h="6" :tone="3" />
          <span class="rc-actions-sep" />
          <Bar :w="52" :h="6" :tone="3" />
        </div>
      </div>
    </div>
  </Stage>
</template>
