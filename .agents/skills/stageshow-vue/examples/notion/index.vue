<script setup lang="ts">
import {
  Check as Tick,
  ChevronDown,
  ChevronsRight,
  Ellipsis,
  FileText,
  GripVertical,
  Heading1,
  Heading2,
  Heading3,
  House,
  Inbox,
  List,
  ListOrdered,
  Plus,
  Search,
  SquareCheck,
  Star,
  Type,
} from 'lucide-vue-next'
import { Fragment, h, type Component } from 'vue'
import { Bar, Menu, Popover, Stage, Text, Window, type Act } from '../../kit'
import './notion.css'

// Notion's slash command. Beats: click into an empty line, press "/", the
// block menu opens, pick "To-do list", type a task, tick it off. The finished
// task stays checked until the host's Replay starts on the empty line.
// Real words: the page title, the placeholder, the menu, the task.

type S = {
  focus: boolean
  slash: boolean
  menu: boolean
  active: number | undefined
  todo: boolean
  task: string
  typing: boolean
  done: boolean
}

const initial: S = {
  focus: false,
  slash: false,
  menu: false,
  active: 0,
  todo: false,
  task: '',
  typing: false,
  done: false,
}

const TITLE = 'Launch plan'
const TASK = 'Send launch email'

type Item = { label: string; hint: string; icon: Component }
const ITEMS: Item[] = [
  { label: 'Text', hint: '', icon: Type },
  { label: 'Heading 1', hint: '#', icon: Heading1 },
  { label: 'Heading 2', hint: '##', icon: Heading2 },
  { label: 'Heading 3', hint: '###', icon: Heading3 },
  { label: 'Bulleted list', hint: '-', icon: List },
  { label: 'Numbered list', hint: '1.', icon: ListOrdered },
  { label: 'To-do list', hint: '[]', icon: SquareCheck },
]
const TODO = ITEMS.findIndex((i) => i.label === 'To-do list')

const MENU_TARGETS = ITEMS.map((_, i) => `item-${i}`)
const MENU_ITEMS = ITEMS.map(({ label, hint, icon: Icon }) =>
  Object.assign(
    h(Fragment, [
      h('span', { class: 'nt-menu__icon' }, [h(Icon, { size: 18, strokeWidth: 1.75 })]),
      h('span', { class: 'nt-menu__label' }, label),
      h('span', { class: 'nt-menu__hint' }, hint),
    ]),
    { render: true },
  ),
)

async function script(a: Act<S>) {
  await a.wait(500)

  // Click into the empty line under the paragraph
  await a.click({ at: 'line', x: 0.72, y: 0.5 })
  await a.set({ focus: true })
  await a.wait(600)

  // "/" opens the block menu, its first row selected
  a.mark('slash')
  await a.key('/')
  await a.set({ slash: true })
  await a.wait(90)
  await a.set({ menu: true })
  await a.wait(800)

  // The pointer takes over the selection, then runs down to To-do list
  await a.move({ at: 'item-0', x: 0.62, y: 0.55 })
  await a.set({ active: undefined })
  await a.wait(200)
  await a.move({ at: `item-${TODO}`, x: 0.62, y: 0.6 })
  await a.wait(350)
  a.mark('pick')
  await a.click()
  await a.set({ menu: false, todo: true })
  await a.wait(650)

  // Type the task
  await a.set({ typing: true })
  await a.type('task', TASK, { interval: 65 })
  await a.set({ typing: false })
  await a.wait(500)

  // Tick it off
  await a.click({ at: 'check', x: 0.72, y: 0.78 })
  a.mark('tick')
  await a.set({ done: true, focus: false })
  await a.wait(2200)

  // Step away and keep the completed task visible. Replay is the reset.
  await a.move({ at: 'rest', x: 0.5, y: 0.5 })
  a.mark('done')
}

const TOP_NAV = [
  { Icon: Search, w: 40 },
  { Icon: House, w: 34 },
  { Icon: Inbox, w: 38 },
]
const DOC_ROWS = [62, 0, 48, 70, 54]
</script>

<template>
  <Stage
    play="once"
    :width="720"
    :height="538"
    :compact="{ below: 600, width: 400, height: 494 }"
    :initial="initial"
    :poster="{ ...initial, todo: true, task: TASK, done: true }"
    :script="script"
    :cursor="{ at: { at: 'rest', x: 0.5, y: 0.5 } }"
    :keys="{ wide: 'bottom-left', compact: 'bottom-right' }"
    accent="#2383e2"
    class="nt"
    v-slot="{ state: s, layout }"
  >
    <Window class="nt-window" :sidebar-width="224">
      <template v-if="layout !== 'compact'" #sidebar>
        <div class="nt-side">
          <div class="nt-ws">
            <span class="nt-ws__mark">B</span>
            <Bar :w="74" :h="7" :tone="4" />
            <ChevronDown :size="13" :stroke-width="2" class="nt-ico-faint" />
          </div>
          <div class="nt-nav">
            <div v-for="(item, i) in TOP_NAV" :key="i" class="nt-nav__row">
              <component :is="item.Icon" :size="16" :stroke-width="1.75" class="nt-ico" />
              <Bar :w="item.w" :h="6" :tone="3" />
            </div>
          </div>
          <div class="nt-section">
            <Bar :w="36" :h="5" :tone="2" />
          </div>
          <div class="nt-nav">
            <div v-for="(w, i) in DOC_ROWS" :key="i" class="nt-nav__row" :data-active="w === 0 || undefined">
              <FileText :size="16" :stroke-width="1.75" class="nt-ico" />
              <Text v-if="w === 0" class="nt-nav__label">{{ TITLE }}</Text>
              <Bar v-else :w="w" :h="6" :tone="3" />
            </div>
          </div>
        </div>
      </template>

      <template #lead>
        <span class="nt-crumb">
          <ChevronsRight
            v-if="layout === 'compact'"
            :size="16"
            :stroke-width="1.75"
            class="nt-ico nt-crumb__toggle"
          />
          <FileText :size="14" :stroke-width="1.75" class="nt-ico" />
          <Text class="nt-crumb__label">{{ TITLE }}</Text>
        </span>
      </template>

      <template v-if="layout !== 'compact'" #toolbar>
        <span class="nt-tools">
          <span class="nt-share">Share</span>
          <Star :size="16" :stroke-width="1.75" class="nt-ico" />
          <Ellipsis :size="16" :stroke-width="1.75" class="nt-ico" />
        </span>
      </template>

      <div class="nt-page">
        <div class="nt-title">{{ TITLE }}</div>
        <div class="nt-block">
          <Bar w="92%" :h="7" :tone="3" />
        </div>
        <div class="nt-block">
          <Bar w="58%" :h="7" :tone="3" />
        </div>

        <!-- The line the story happens on: a text line that becomes a to-do -->
        <div class="nt-line" data-target="line" data-cursor="ibeam">
          <span class="nt-handle" aria-hidden="true">
            <Plus :size="16" :stroke-width="1.75" />
            <GripVertical :size="16" :stroke-width="1.75" />
          </span>

          <div class="nt-layer nt-text" :data-show="!s.todo || undefined">
            <span v-if="s.slash" class="nt-slash">/</span>
            <span class="nt-caret" :data-show="(s.focus && !s.todo) || undefined" />
            <span class="nt-placeholder" :data-show="(s.focus && !s.slash) || undefined">
              Press ‘/’ for commands
            </span>
          </div>

          <div
            class="nt-layer nt-todo"
            :data-show="s.todo || undefined"
            :data-done="s.done || undefined"
          >
            <span class="nt-box" data-target="check" data-cursor="hand">
              <Tick :size="12" :stroke-width="3.25" />
            </span>
            <span class="nt-todo__text">
              {{ s.task }}
              <span
                class="nt-caret"
                :data-show="(s.focus && s.todo) || undefined"
                :data-typing="s.typing || undefined"
              />
              <span class="nt-placeholder" :data-show="(s.focus && !s.task) || undefined">
                To-do
              </span>
            </span>
          </div>

          <Popover :show="s.menu" class="nt-menu" origin="top left">
            <div class="nt-menu__head">Basic blocks</div>
            <Menu
              class="nt-items"
              :value="s.active"
              :targets="MENU_TARGETS"
              :items="MENU_ITEMS"
            />
          </Popover>
        </div>

        <div class="nt-block nt-h2">
          <Bar :w="120" :h="10" :tone="4" />
        </div>
        <div class="nt-block">
          <Bar w="84%" :h="7" :tone="3" />
        </div>
        <div class="nt-block">
          <Bar w="66%" :h="7" :tone="3" />
        </div>
      </div>
    </Window>
    <!-- Where the pointer rests between loops, over the page's empty right side -->
    <span class="nt-rest" data-target="rest" />
  </Stage>
</template>
