<script setup lang="ts">
import {
  Box,
  ChevronDown,
  CircleDashed,
  Folder,
  Inbox,
  IterationCcw,
  Layers,
  ListFilter,
  Search,
  SignalHigh,
  SlidersHorizontal,
  SquarePen,
  Tag,
  UserRound,
  UserRoundCheck,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import { Avatar, Bar, Camera, Collapse, Field, Popover, Stage, Text, Window, type Act, type Rect } from '../../kit'
import './linear.css'

// Linear, light, in its desktop window (860 wide), as it looks after the
// 2026 refresh: grayscale chrome, a dimmed sidebar, compact rounded tabs.
// Color stays only on Linear's own content marks (status circles, label
// dots, avatars) and the accent on the one avatar the story lands. The issue list is the
// context; Cmd+K opens the command menu over it, "assign" filters it, the
// user picks "Assign to me", and ENG-142's row takes their avatar while its
// status turns from Todo to In Progress. Cmd+Z undoes it, so the loop closes
// with a caused reset.
//
// Real strings: the team, the view, ENG-142 and its title, the command menu
// (its rows are what the typing filters, so they must be words), and what is
// typed. Every other row is placeholder lines around Linear's own signature
// marks: priority bars, status circles, avatars.
//
// Icons: Linear ships no public icon pack, so the nav and command glyphs are
// lucide-vue-next, chosen for its thin, even line, which is
// close to Linear's own. The status circles and priority bars are Linear's
// own geometry, drawn from circles and rects, because they are its content.

type S = {
  focus: boolean
  open: boolean
  query: string
  hoverMe: boolean
  assigned: boolean
  zoom: Rect | null
}

const initial: S = { focus: false, open: false, query: '', hoverMe: false, assigned: false, zoom: null }

type Status = 'backlog' | 'todo' | 'progress' | 'done'
type Row = { status: Status; pri: 0 | 1 | 2 | 3 | 4; id: number; title: number; label?: number; who?: string; date: number }

const ROWS: Row[] = [
  { status: 'progress', pri: 4, id: 44, title: 210, label: 34, who: 'Mara', date: 30 },
  { status: 'progress', pri: 2, id: 40, title: 168, who: 'Theo', date: 26 },
  { status: 'todo', pri: 3, id: 0, title: 0, label: 30, date: 30 }, // ENG-142
  { status: 'todo', pri: 2, id: 42, title: 236, who: 'Ines', date: 28 },
  { status: 'todo', pri: 1, id: 38, title: 150, label: 40, date: 30 },
  { status: 'backlog', pri: 0, id: 44, title: 192, who: 'Mara', date: 24 },
  { status: 'backlog', pri: 2, id: 40, title: 128, date: 30 },
  { status: 'backlog', pri: 3, id: 42, title: 178, who: 'Theo', date: 28 },
  { status: 'done', pri: 1, id: 38, title: 204, date: 26 },
  { status: 'done', pri: 2, id: 44, title: 140, who: 'Ines', date: 30 },
  { status: 'done', pri: 0, id: 40, title: 186, who: 'Mara', date: 28 },
  { status: 'done', pri: 3, id: 42, title: 122, date: 24 },
]

const COMMANDS: { label: string; key: string; icon: Component; target?: string }[] = [
  { label: 'Change status…', key: 'S', icon: CircleDashed },
  { label: 'Assign to…', key: 'A', icon: UserRound },
  { label: 'Assign to me', key: 'I', icon: UserRoundCheck, target: 'me' },
  { label: 'Change priority…', key: 'P', icon: SignalHigh },
  { label: 'Add labels…', key: 'L', icon: Tag },
]

const REST = { at: 'rest', x: 0.64, y: 0.5 }

async function script(a: Act<S>) {
  const compact = a.layout === 'compact'
  await a.wait(900)

  // 1. Context: the pointer comes to rest on ENG-142, which takes focus
  a.mark('focus')
  await a.move({ at: 'row', x: compact ? 0.86 : 0.7, y: 0.6 })
  await a.set({ focus: true })
  await a.wait(700)

  // 2. Cmd+K opens the command menu on that issue
  a.mark('open')
  await a.key('cmd+k')
  await a.set({ open: true })
  await a.wait(800)

  // 3. Type "assign": the menu narrows to the two assign commands
  a.mark('type')
  await a.type('query', 'assign', { interval: 95 })
  await a.wait(700)

  // 4. Pick yourself
  a.mark('pick')
  await a.move({ at: 'me', x: 0.62, y: 0.55 })
  await a.set({ hoverMe: true })
  await a.wait(350)
  await a.click()
  await a.wait(120)
  await a.set({ open: false })
  // Step the pointer off the row so it doesn't sit over the change
  await a.move({ at: 'rest', x: compact ? 0.5 : 0.42, y: 0.5 })

  // 5. The camera comes in on the row (the change is two 16px marks in a
  // 920px scene), then the row updates: avatar in, Todo -> In Progress
  a.mark('result')
  if (!compact) {
    const who = a.rect('who142', { layout: true })
    const row = a.rect('row', { layout: true })
    await a.set({ zoom: { x: row.x, y: row.y, width: who.x + who.width + 12 - row.x, height: row.height } })
    await a.wait(900)
  }
  await a.set({ assigned: true })
  await a.wait(2200)
  if (!compact) {
    await a.set({ zoom: null })
    await a.wait(1100)
  }

  // Undo, the way Linear does it, then let go of the row
  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ assigned: false })
  await a.wait(900)
  await a.snap({ query: '', hoverMe: false })
  await a.move(REST)
  await a.set({ focus: false })
  await a.wait(900)
}

function rowStatus(r: Row, i: number, s: S): Status {
  return i === 2 && s.assigned ? 'progress' : r.status
}

function firstMatchIndex(q: string): number {
  const ql = q.toLowerCase()
  return COMMANDS.findIndex((x) => !ql || x.label.toLowerCase().includes(ql))
}
</script>

<template>
  <Stage
    :width="920"
    :height="470"
    :compact="{ below: 600, width: 420, height: 340 }"
    accent="#5e6ad2"
    :initial="initial"
    :poster="{ ...initial, focus: true, assigned: true }"
    :script="script"
    :cursor="{ at: REST }"
    class="ln-stage"
    v-slot="{ state: s, layout }"
  >
    <Camera :focus="s.zoom" :max="1.6" :pad="20" :feather="44">
      <Window
        class="ln-window"
        :body="{ className: 'ln-body', 'data-crop': true }"
        :sidebar-width="212"
      >
        <template v-if="layout !== 'compact'" #sidebar>
          <div class="ln-side">
            <div class="ln-workspace">
              <span class="ln-workspace__tile">A</span>
              <Bar :w="46" :h="6" :tone="4" />
              <ChevronDown :size="12" :stroke-width="1.8" class="ln-icon" />
              <span class="ss-window__spacer" />
              <Search :size="14" :stroke-width="1.7" class="ln-icon" />
              <span class="ln-compose">
                <SquarePen :size="13" :stroke-width="1.7" class="ln-icon" />
              </span>
            </div>
            <div class="ln-group">
              <div class="ln-nav">
                <Inbox :size="14" :stroke-width="1.7" class="ln-icon" />
                <Bar :w="34" :h="5" :tone="3" />
              </div>
              <div class="ln-nav">
                <UserRound :size="14" :stroke-width="1.7" class="ln-icon" />
                <Bar :w="52" :h="5" :tone="3" />
              </div>
            </div>
            <div class="ln-group">
              <div class="ln-section"><Bar :w="58" :h="5" :tone="2" /></div>
              <div class="ln-nav ln-team">
                <span class="ln-team__tile">E</span>
                <Text class="ln-team__name">Engineering</Text>
                <ChevronDown :size="11" :stroke-width="1.8" class="ln-icon" />
              </div>
              <div class="ln-sub">
                <div class="ln-nav" data-active>
                  <Layers :size="14" :stroke-width="1.7" class="ln-icon ln-icon--on" />
                  <Text class="ln-nav__label">Issues</Text>
                </div>
                <div class="ln-nav">
                  <IterationCcw :size="14" :stroke-width="1.7" class="ln-icon" />
                  <Bar :w="38" :h="5" :tone="3" />
                </div>
                <div class="ln-nav">
                  <Box :size="14" :stroke-width="1.7" class="ln-icon" />
                  <Bar :w="46" :h="5" :tone="3" />
                </div>
              </div>
            </div>
            <div class="ln-group">
              <div class="ln-section"><Bar :w="44" :h="5" :tone="2" /></div>
              <div class="ln-nav">
                <Folder :size="14" :stroke-width="1.7" class="ln-icon" />
                <Bar :w="56" :h="5" :tone="3" />
              </div>
              <div class="ln-nav">
                <Folder :size="14" :stroke-width="1.7" class="ln-icon" />
                <Bar :w="42" :h="5" :tone="3" />
              </div>
            </div>
          </div>
        </template>

        <template #lead>
          <div class="ln-crumbs">
            <span v-if="layout === 'compact'" class="ln-team__tile">E</span>
            <Text class="ln-crumbs__team">{{ layout === 'compact' ? 'Issues' : 'Engineering' }}</Text>
            <div v-if="layout !== 'compact'" class="ln-tabs">
              <span class="ln-tab" data-active>
                <Text>All issues</Text>
              </span>
              <span class="ln-tab"><Bar :w="34" :h="5" :tone="3" /></span>
              <span class="ln-tab"><Bar :w="42" :h="5" :tone="3" /></span>
            </div>
          </div>
        </template>

        <template #toolbar>
          <div class="ln-tools">
            <span class="ln-tool"><ListFilter :size="14" :stroke-width="1.7" class="ln-icon" /></span>
            <span class="ln-tool ln-tool--display">
              <SlidersHorizontal :size="13" :stroke-width="1.7" class="ln-icon" />
              <Bar v-if="layout !== 'compact'" :w="36" :h="5" :tone="3" />
            </span>
          </div>
        </template>

        <div class="ln-list">
          <div
            v-for="(r, i) in ROWS"
            :key="i"
            class="ln-row"
            :data-target="i === 2 ? 'row' : i === 6 ? 'rest' : undefined"
            :data-focus="(i === 2 && s.focus) || undefined"
          >
            <!-- Priority -->
            <svg v-if="r.pri === 0" class="ln-pri" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <rect v-for="x in [2, 6, 10]" :key="x" :x="x - 0.75" y="6.25" width="2.5" height="1.5" rx="0.5" />
            </svg>
            <svg v-else-if="r.pri === 4" class="ln-pri" data-urgent width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <rect x="1" y="1" width="12" height="12" rx="3" />
              <rect class="ln-pri__mark" x="6.25" y="3.5" width="1.5" height="4.5" rx="0.75" />
              <rect class="ln-pri__mark" x="6.25" y="9.25" width="1.5" height="1.5" rx="0.75" />
            </svg>
            <svg v-else class="ln-pri" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <rect
                v-for="idx in [0, 1, 2]"
                :key="idx"
                :x="1.5 + idx * 4"
                :y="8 - idx * 3"
                width="3"
                :height="4 + idx * 3"
                rx="1"
                :data-on="idx < r.pri || undefined"
              />
            </svg>

            <span class="ln-id">
              <Text v-if="i === 2" :tone="2">ENG-142</Text>
              <Bar v-else :w="r.id" :h="5" :tone="2" />
            </span>

            <!-- StatusIcon -->
            <span v-if="i === 2" class="ln-st" data-target="st142">
              <svg class="ln-status" :data-status="rowStatus(r, i, s)" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                <circle class="ln-status__ring" cx="7" cy="7" r="5.5" fill="none" stroke-width="1.5" />
                <circle class="ln-status__pie" cx="7" cy="7" r="1.75" fill="none" stroke-width="3.5" pathLength="100" transform="rotate(-90 7 7)" />
              </svg>
            </span>
            <svg v-else-if="r.status === 'backlog'" class="ln-status" data-status="backlog" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <circle cx="7" cy="7" r="5.5" fill="none" stroke-width="1.5" stroke-dasharray="2.1 1.5" />
            </svg>
            <svg v-else-if="r.status === 'done'" class="ln-status" data-status="done" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <circle cx="7" cy="7" r="6.25" />
              <path d="M4.4 7.2 6.2 9l3.4-3.6" fill="none" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else class="ln-status" :data-status="r.status" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <circle class="ln-status__ring" cx="7" cy="7" r="5.5" fill="none" stroke-width="1.5" />
              <circle class="ln-status__pie" cx="7" cy="7" r="1.75" fill="none" stroke-width="3.5" pathLength="100" transform="rotate(-90 7 7)" />
            </svg>

            <span class="ln-title">
              <Text v-if="i === 2" class="ln-title__text">Fix login redirect loop</Text>
              <Bar v-else :w="layout === 'compact' ? Math.min(r.title, 150) : r.title" :h="6" :tone="3" />
            </span>

            <span v-if="layout !== 'compact'" class="ln-labels">
              <span v-if="r.label" class="ln-chip">
                <span class="ln-chip__dot" :data-tone="i % 3" />
                <Bar :w="r.label" :h="5" :tone="3" />
              </span>
            </span>

            <span class="ln-who">
              <span v-if="i === 2" class="ln-who__swap" data-target="who142" :data-assigned="s.assigned || undefined">
                <svg class="ln-unassigned" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                  <circle cx="9" cy="9" r="8" fill="none" stroke-width="1.2" stroke-dasharray="2 1.6" />
                  <circle cx="9" cy="7.2" r="2.1" />
                  <path d="M5.4 13.1a3.9 3.9 0 0 1 7.2 0z" />
                </svg>
                <Avatar name="Maya" :size="18" tone="accent" class="ln-who__me" :style="{ fontSize: '9.5px' }" />
              </span>
              <Avatar v-else-if="r.who" :name="r.who" :size="18" class="ln-avatar" :data-face="i % 3" :style="{ fontSize: '9.5px' }" />
              <svg v-else class="ln-unassigned" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <circle cx="9" cy="9" r="8" fill="none" stroke-width="1.2" stroke-dasharray="2 1.6" />
                <circle cx="9" cy="7.2" r="2.1" />
                <path d="M5.4 13.1a3.9 3.9 0 0 1 7.2 0z" />
              </svg>
            </span>

            <span v-if="layout !== 'compact'" class="ln-date">
              <Bar :w="r.date" :h="5" :tone="2" />
            </span>
          </div>
        </div>
      </Window>

      <div class="ln-scrim" :data-show="s.open || undefined" />
      <Popover :show="s.open" origin="top center" class="ln-cmd">
        <div class="ln-cmd__context">
          <span class="ln-cmd__chip">
            <Text>ENG-142</Text>
            <Text class="ln-cmd__chip-title">Fix login redirect loop</Text>
          </span>
        </div>
        <Field :value="s.query" placeholder="Type a command or search…" :focused="s.open" class="ln-cmd__field" :box="{ 'data-cursor': 'pointer' }" />
        <div class="ln-cmd__list">
          <!-- Compact keeps the first three, so the menu clears the keycaps -->
          <Collapse
            v-for="(c, i) in layout === 'compact' ? COMMANDS.slice(0, 3) : COMMANDS"
            :key="c.label"
            :open="!s.query || c.label.toLowerCase().includes(s.query.toLowerCase())"
          >
            <div
              class="ln-cmd__item"
              :data-target="c.target"
              :data-active="(s.hoverMe ? c.target === 'me' : i === firstMatchIndex(s.query)) || undefined"
            >
              <span class="ln-cmd__icon">
                <component :is="c.icon" :size="15" :stroke-width="1.6" />
              </span>
              <Text class="ln-cmd__label">{{ c.label }}</Text>
              <span class="ln-cmd__key">{{ c.key }}</span>
            </div>
          </Collapse>
        </div>
      </Popover>
    </Camera>
  </Stage>
</template>
