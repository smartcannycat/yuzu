<script lang="ts">
export const compositionLessons = [
  { id: 'framing', title: 'Give the product room', note: 'The same exports window and status in a small frame. Protect the header and useful rows; let the window continue beyond a deliberate edge.', bad: 'Tight edges and a status over the content', good: 'Clear gutters and an intentional bottom crop' },
  { id: 'ui-anatomy', title: 'Make the UI read like a product', note: 'The same project, tasks and action. Type hierarchy and shared alignment make the relationships clear without adding decoration.', bad: 'Labels, metadata and actions compete', good: 'A clear heading and consistent reading columns' },
  { id: 'visual-restraint', title: 'Choose where emphasis belongs', note: 'The same plan details and action. When every edge and value is emphasized, the primary action loses its place.', bad: 'Borders, shadows and color on every part', good: 'Quiet details and one clear action' },
  { id: 'compact-reflow', title: 'Reflow a small composition', note: 'The same three tasks in a 300px slot. A smaller host needs a readable arrangement, not a miniature desktop table.', bad: 'The desktop table is scaled to half size', good: 'The same content reflows at readable sizes' },
  { id: 'edge-separation', title: 'Make edges feel deliberate', note: 'The same sync panel and confirmation. Nearly touching edges look accidental; a clear gap makes two surfaces easy to distinguish.', bad: 'The confirmation almost touches the panel', good: 'A deliberate gap separates the two surfaces' },
  { id: 'nested-spacing', title: 'Carry padding around every edge', note: 'The same preferences and action. Check the bottom and the corners as carefully as the space above the first label.', bad: 'The inner surface and action crowd the bottom', good: 'Each layer has a consistent inset' },
  { id: 'control-alignment', title: 'Fit the contents of a control', note: 'The same search field and actions. Shared content alignment balances labels and icons within their actual controls.', bad: 'Icons sit low and labels crowd the upper edge', good: 'Icons and labels share a balanced content row' },
  { id: 'content-density', title: 'Give whitespace a job', note: 'The same three appointments. Keep each time with its subject and separate the appointments, rather than spreading every line equally.', bad: 'Uniform gaps weaken the appointment groups', good: 'Tighter groups make the schedule easier to scan' },
  { id: 'surface-contrast', title: 'Keep the foreground readable', note: 'The same sharing controls on a tinted ground. A quiet surface still needs enough contrast for its text and available actions.', bad: 'Foreground, surface and ground blend together', good: 'Readable text and a distinct foreground surface' },
  { id: 'icon-consistency', title: 'Give icons a shared construction', note: 'The same three destinations. Similar boxes do not guarantee similar visual weight; compare the shapes, stroke and visible size.', bad: 'Mixed fill, stroke weight and visible size', good: 'One construction with balanced optical weight' },
  { id: 'decorative-noise', title: 'Let the information lead', note: 'The same activity report and chart. Gradients and glow can compete with a useful result even when the layout is orderly.', bad: 'Decorative effects compete with the report', good: 'The value and chart carry the emphasis' },
  { id: 'product-anatomy', title: 'Choose chrome that serves the task', note: 'The same document, permission and sharing action. Familiar browser shapes are misleading when the task is a small sharing panel.', bad: 'Browser chrome disguises a sharing task', good: 'Document, permission and action have clear roles' },
  { id: 'unread-gutter', title: 'Never push only the unread rows in', note: 'The same inbox with two unread messages. An unread dot must not move its row: pushing only unread rows in makes the column zigzag, and every read changes the layout. Hang the dot in the margin, as here, reserve a dot column on every row as Mail and Messages do, or put it by the time as Gmail does; follow the product.', bad: 'Unread rows push their avatar in; the column zigzags', good: 'Every avatar on one edge; the dot hangs in the margin' },
] as const

export type LessonId = typeof compositionLessons[number]['id']
</script>

<script setup lang="ts">
import { computed, defineComponent, h, type PropType } from 'vue'
import { Avatar, Row, Stage } from '../kit'
import './contrasts.css'
import './composition.css'

const props = defineProps<{
  lessonId: string
}>()

const lesson = computed(() => compositionLessons.find((item) => item.id === props.lessonId))
const height = 302

const EXPORTS = [
  ['Campaign assets', '24 files'],
  ['Brand library', '18 files'],
  ['Product launch', '32 files'],
  ['Homepage', '8 files'],
] as const

const TASKS = [
  { name: 'Design review', owner: 'Maya', due: 'Today', status: 'Ready' },
  { name: 'Onboarding', owner: 'Jon', due: 'Tomorrow', status: 'In review' },
  { name: 'Billing audit', owner: 'Ana', due: 'Friday', status: 'Ready' },
] as const

const APPOINTMENTS = [
  ['9:30 AM', 'Design review', 'Maya and Jon'],
  ['11:00 AM', 'Customer call', 'Ana · 30 minutes'],
  ['2:00 PM', 'Planning', 'Product team'],
] as const

type SymbolName = 'check' | 'search' | 'download' | 'arrow' | 'folder' | 'inbox' | 'archive' | 'link' | 'chevron'

const SYMBOL_PATHS: Record<SymbolName, string> = {
  check: 'm4.5 10 3.5 3.5 7.5-7.5',
  search: 'M14 8.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0Zm-1.5 4 4 4',
  download: 'M10 3v9m-3-3 3 3 3-3M4 13v4h12v-4',
  arrow: 'M4 10h12m-5-5 5 5-5 5',
  folder: 'M2.5 5.5h6l2 2h7v9h-15z',
  inbox: 'M3 4h14v12H3V4Zm0 7h4l1.5 2h3l1.5-2h4',
  archive: 'M3 3.5h14v4H3zM4.5 7.5v9h11v-9M8 11h4',
  link: 'm8 12 4-4M7 13H5a3 3 0 0 1 0-6h3m4 0h3a3 3 0 0 1 0 6h-2',
  chevron: 'm6 8 4 4 4-4',
}

const SymbolIcon = defineComponent({
  props: {
    name: { type: String as PropType<SymbolName>, required: true },
    className: { type: String, default: '' },
  },
  setup(p) {
    return () =>
      h(
        'svg',
        { class: `cp-symbol ${p.className}`, width: '18', height: '18', viewBox: '0 0 20 20', 'aria-hidden': 'true' },
        [h('path', { d: SYMBOL_PATHS[p.name] })],
      )
  },
})

const FileIcon = defineComponent({
  setup() {
    return () =>
      h(
        'svg',
        { class: 'cp-file', width: '16', height: '18', viewBox: '0 0 16 18', 'aria-hidden': 'true' },
        [h('path', { d: 'M3 1.5h6l4 4v11H3zM9 1.5v4h4M5.5 9h5M5.5 12h5' })],
      )
  },
})

const ICON_ITEMS: { icon: SymbolName; title: string; count: string }[] = [
  { icon: 'inbox', title: 'Inbox', count: '4' },
  { icon: 'folder', title: 'Project files', count: '24' },
  { icon: 'archive', title: 'Archive', count: '12' },
]

const ACTIVITY_BARS = [20, 26, 18, 28, 32] as const
const ACTIVITY_DAYS = ['M', 'T', 'W', 'T', 'F'] as const

const INBOX = [
  ['Maya Chen', 'Launch checklist', true],
  ['Jon Park', 'Re: pricing page', false],
  ['Ana Ruiz', 'Q3 board deck', true],
] as const
</script>

<template>
  <section v-if="lesson" class="cp-lesson">
    <header>
      <div>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.note }}</p>
      </div>
    </header>
    <Stage :width="704" :height="height" :compact="{ below: 704, width: 340, height: height * 2 + 16 }" class="tc-stage">
      <div class="tc-pair cp-pair" :data-composition="lesson.id">
        <figure v-for="good in [false, true]" :key="String(good)">
          <div class="tc-visual">
            <!-- unread-gutter -->
            <div v-if="lesson.id === 'unread-gutter'" class="cp-inbox" :data-shove="!good || undefined">
              <h3>Inbox</h3>
              <Row
                v-for="[name, subject, unread] in INBOX"
                :key="name"
                :title="name"
                :subtitle="subject"
                meta="9:41"
                :unread="unread"
              >
                <template #lead>
                  <Avatar :name="name" :size="28" />
                </template>
              </Row>
            </div>

            <!-- framing -->
            <div v-else-if="lesson.id === 'framing'" class="cp-frame" :data-good="good || undefined">
              <div class="cp-export-window">
                <div class="cp-window-bar">
                  <span class="cp-window-dots" aria-hidden="true"><i /><i /><i /></span>
                  <span>Exports</span>
                </div>
                <div class="cp-export-heading">
                  <strong>Recent exports</strong>
                  <span>This week</span>
                </div>
                <div v-for="[name, count] in EXPORTS" :key="name" class="cp-export-row">
                  <FileIcon />
                  <span>{{ name }}<small>{{ count }}</small></span>
                  <span class="cp-ready">Ready</span>
                </div>
              </div>
              <div class="cp-export-status">
                <span class="cp-status-dot" />
                Export complete
                <small>24 files saved</small>
              </div>
            </div>

            <!-- ui-anatomy -->
            <div v-else-if="lesson.id === 'ui-anatomy'" class="cp-anatomy" :data-good="good || undefined">
              <div class="cp-project-head">
                <span class="cp-project-icon"><FileIcon /></span>
                <div>
                  <h3>Release checklist</h3>
                  <p>Due Friday · 4 tasks</p>
                </div>
              </div>
              <div class="cp-project-rows">
                <div><span>Review copy</span><small>Ready</small></div>
                <div><span>Test mobile</span><small>In review</small></div>
              </div>
              <div class="cp-project-foot">
                <span>2 tasks remaining</span>
                <span class="cp-action">Open project</span>
              </div>
            </div>

            <!-- visual-restraint -->
            <div v-else-if="lesson.id === 'visual-restraint'" class="cp-plan" :data-good="good || undefined">
              <div class="cp-plan-head">
                <h3>Starter plan</h3>
                <span class="cp-plan-badge">Active</span>
              </div>
              <div class="cp-plan-price"><strong>$24</strong><span>/ month</span></div>
              <div class="cp-plan-seats"><span>Team seats</span><span>3 of 5 seats</span></div>
              <span class="cp-action">Manage plan</span>
            </div>

            <!-- compact-reflow -->
            <div v-else-if="lesson.id === 'compact-reflow'" class="cp-tasks" :data-good="good || undefined">
              <div class="cp-task-design">
                <div class="cp-task-head"><h3>Project tasks</h3><span>3 open</span></div>
                <div class="cp-task-columns"><span>Task</span><span>Owner</span><span>Due</span><span>Status</span></div>
                <div v-for="task in TASKS" :key="task.name" class="cp-task-row">
                  <span class="cp-task-name">{{ task.name }}</span>
                  <span class="cp-task-owner">{{ task.owner }}</span>
                  <span class="cp-task-due">{{ task.due }}</span>
                  <span class="cp-task-status">{{ task.status }}</span>
                </div>
              </div>
            </div>

            <!-- edge-separation -->
            <div v-else-if="lesson.id === 'edge-separation'" class="cp-edges" :data-good="good || undefined">
              <div class="cp-sync-panel">
                <h3>Workspace sync</h3>
                <div><span>Design library</span><small>Up to date</small></div>
                <div><span>Brand assets</span><small>2 min ago</small></div>
              </div>
              <div class="cp-sync-status">
                <SymbolIcon name="check" />
                <span>All files synced</span>
              </div>
            </div>

            <!-- nested-spacing -->
            <div v-else-if="lesson.id === 'nested-spacing'" class="cp-nesting" :data-good="good || undefined">
              <div class="cp-preferences">
                <h3>Weekly summary</h3>
                <div class="cp-preference-row">
                  <span>Send by email</span>
                  <span class="cp-toggle"><i /></span>
                </div>
                <div class="cp-preference-row">
                  <span>Every Monday</span>
                  <small>9:00 AM</small>
                </div>
                <span class="cp-action">Save preferences</span>
              </div>
            </div>

            <!-- control-alignment -->
            <div v-else-if="lesson.id === 'control-alignment'" class="cp-controls-study" :data-good="good || undefined">
              <h3>Project files</h3>
              <div class="cp-search-control">
                <SymbolIcon name="search" />
                <span>Search files</span>
              </div>
              <div class="cp-control-actions">
                <span class="cp-export-control">
                  <SymbolIcon name="download" />
                  <span>Export files</span>
                </span>
                <span class="cp-preview-control">
                  <span>Preview</span>
                  <SymbolIcon name="arrow" />
                </span>
              </div>
            </div>

            <!-- content-density -->
            <div v-else-if="lesson.id === 'content-density'" class="cp-density" :data-good="good || undefined">
              <div class="cp-density-head">
                <h3>Today</h3>
                <span>Wednesday, 14 May</span>
              </div>
              <div v-for="[time, title, people] in APPOINTMENTS" :key="time" class="cp-appointment">
                <time>{{ time }}</time>
                <div>
                  <strong>{{ title }}</strong>
                  <small>{{ people }}</small>
                </div>
              </div>
            </div>

            <!-- surface-contrast -->
            <div v-else-if="lesson.id === 'surface-contrast'" class="cp-contrast-ground" :data-good="good || undefined">
              <div class="cp-contrast-panel">
                <h3>Share document</h3>
                <p>Launch brief</p>
                <div class="cp-access-row">
                  <span>Anyone with the link</span>
                  <span>Can view</span>
                </div>
                <span class="cp-action"><SymbolIcon name="link" />Copy link</span>
              </div>
            </div>

            <!-- icon-consistency -->
            <div v-else-if="lesson.id === 'icon-consistency'" class="cp-icon-list" :data-good="good || undefined">
              <h3>Workspace</h3>
              <div v-for="item in ICON_ITEMS" :key="item.icon" class="cp-icon-row">
                <span :class="`cp-icon-slot cp-icon-${item.icon}`"><SymbolIcon :name="item.icon" /></span>
                <span>{{ item.title }}</span>
                <small>{{ item.count }}</small>
              </div>
            </div>

            <!-- decorative-noise -->
            <div v-else-if="lesson.id === 'decorative-noise'" class="cp-decoration" :data-good="good || undefined">
              <h3>Weekly activity</h3>
              <div class="cp-activity-total">
                <strong>124</strong>
                <span>tasks completed</span>
              </div>
              <p>18 more than last week</p>
              <div class="cp-activity-chart" aria-label="Daily tasks: Monday 20, Tuesday 26, Wednesday 18, Thursday 28, Friday 32">
                <div v-for="(value, i) in ACTIVITY_BARS" :key="i">
                  <i :style="{ height: `${value * 1.3}px` }" />
                  <span>{{ ACTIVITY_DAYS[i] }}</span>
                </div>
              </div>
              <span class="cp-report-link">View report <SymbolIcon name="arrow" /></span>
            </div>

            <!-- product-anatomy -->
            <div v-else class="cp-product" :data-good="good || undefined">
              <div class="cp-product-top">
                <span class="cp-window-dots" aria-hidden="true"><i /><i /><i /></span>
                <h3>Share handoff</h3>
              </div>
              <div class="cp-document">
                <FileIcon />
                <span>Launch brief</span>
              </div>
              <div class="cp-permission">
                <span>Anyone with the link</span>
                <span>Can view <SymbolIcon name="chevron" /></span>
              </div>
              <div class="cp-product-footer">
                <span class="cp-action"><SymbolIcon name="link" />Copy link</span>
              </div>
            </div>
          </div>
          <figcaption>{{ good ? lesson.good : lesson.bad }}</figcaption>
        </figure>
      </div>
    </Stage>
  </section>
</template>
