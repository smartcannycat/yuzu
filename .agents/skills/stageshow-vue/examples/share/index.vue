<script setup lang="ts">
import { h } from 'vue'
import { Check as Tick, ChevronDown, FileText, Lock } from 'lucide-vue-next'
import { Avatar, Bar, Collapse, Facepile, Field, Menu, Popover, Roll, Row, Stage, Text, Window, type Act, type Layout, type Rect } from '../../kit'
import './share.css'

// A document editor's Share popover. Beats: Share opens the popover over the
// document, an email is typed and committed as a chip with Enter, the role
// menu sets Can edit, Invite drops the new person in at the top of the access
// list. Share closes the popover; the list is reset while it is out of sight.
//
// What makes it hold up frame by frame:
// - The popover is measured from the Share button: its right edge is the
//   button's right edge, its top 8px below it. Nothing is hard-coded.
// - The role picker sits inside the field, as wide as its longest label, so
//   Can view to Can edit moves nothing; only the word changes. The field is
//   wide enough for the whole email as text and as a chip.
// - The role menu opens under its trigger and runs to the popover's inner
//   edge, so it covers the role column whole: no word peeks out beside it.
// - The document behind is placeholder bars, so the popover's edge only ever
//   crosses filler, never a word.
// - Every person is the same two-line Row, the new one included.
// - The Enter keycap shows over the document, clear of the popover.
//
// Real strings: the title, the popover's labels, the email, the roles and the
// people. The document behind is placeholder.

type S = {
  open: boolean
  email: string
  typing: boolean
  chip: boolean
  menu: boolean
  role: string
  hover: number | undefined
  added: boolean
}

const initial: S = { open: false, email: '', typing: false, chip: false, menu: false, role: 'Can view', hover: undefined, added: false }

// The still is the payoff: the popover open with the new person added
const poster: S = { ...initial, open: true, added: true }

const DOC = 'Launch brief'
const EMAIL = 'priya@lumen.co'
const ROLES = ['Can view', 'Can comment', 'Can edit']
const EDIT = ROLES.indexOf('Can edit')
const ROLE_TARGETS = ROLES.map((_, i) => `role-${i}`)

async function script(a: Act<S>) {
  await a.wait(600)

  // 1. Share opens the popover; the field takes focus
  a.mark('open')
  await a.click({ at: 'share', x: 0.5, y: 0.55 })
  await a.set({ open: true })
  await a.wait(700)

  // 2. Type the email, then Enter commits it as a chip in place
  a.mark('type')
  await a.click({ at: 'field', x: 0.3, y: 0.5 })
  await a.set({ typing: true })
  await a.type('email', EMAIL, { interval: 55 })
  await a.set({ typing: false })
  await a.wait(250)
  await a.key('enter')
  await a.set({ chip: true })
  await a.wait(600)

  // 3. The role menu: open it, run down to Can edit, pick it
  a.mark('role')
  await a.click({ at: 'role', x: 0.45, y: 0.5 })
  await a.set({ menu: true })
  await a.wait(450)
  await a.move({ at: `role-${EDIT}`, x: 0.4, y: 0.55 })
  await a.wait(300)
  await a.click()
  await a.set({ menu: false, role: 'Can edit' })
  await a.wait(500)

  // 4. Invite: the person drops in at the top of the list, then the field
  //    clears. Two beats: one cause, one effect at a time, so the eye follows
  //    the chip into the list before the field empties behind it
  a.mark('invite')
  await a.click({ at: 'invite', x: 0.5, y: 0.55 })
  await a.set({ added: true })
  await a.wait(350)
  await a.set({ chip: false, email: '', role: 'Can view' })
  await a.wait(1850)

  // 5. Share again closes it; the list resets out of sight
  a.mark('close')
  await a.click({ at: 'share', x: 0.5, y: 0.55 })
  await a.set({ open: false })
  await a.wait(450)
  await a.snap({ added: false })
  await a.wait(500)
}

type Geo = { win: { x: number; y: number; w: number; h: number }; pop: number }

// Wide: one 24px gutter above and either side of the window, which runs off
// the bottom. Compact: the same at the column's width, a narrower popover.
const GEO: Record<Layout, Geo> = {
  wide: { win: { x: 24, y: 24, w: 432, h: 360 }, pop: 344 },
  compact: { win: { x: 16, y: 20, w: 326, h: 400 }, pop: 310 },
}

function popBox(rect: (name: string) => Rect, layout: Layout) {
  const g = GEO[layout]
  const share = rect('share')
  return { left: share.x + share.width - g.pop, top: share.y + share.height + 8, width: g.pop }
}

function popStyle(rect: (name: string) => Rect, layout: Layout) {
  const pop = popBox(rect, layout)
  return { left: `${pop.left}px`, top: `${pop.top}px`, width: `${pop.width}px` }
}

/** The role menu sits 6px under the field, from its trigger's left edge to
 *  6px past the popover's inner edge (over the role column), in the popover's own coordinates. */
function roleMenu(rect: (name: string) => Rect, layout: Layout) {
  const pop = popBox(rect, layout)
  const r = rect('role')
  const f = rect('field')
  const left = r.x - pop.left - 4
  return {
    left: `${left}px`,
    top: `${f.y - pop.top + f.height + 6}px`,
    width: `${pop.width - 10 - left}px`,
  }
}

function roleItems(role: string) {
  return ROLES.map((r) =>
    Object.assign(
      h('span', { class: 'sh-menu__item', key: r }, [
        h('span', { class: 'sh-menu__tick' }, r === role ? [h(Tick, { size: 12, strokeWidth: 2.5 })] : []),
        r,
      ]),
      { render: true },
    ),
  )
}
</script>

<template>
  <Stage
    :width="480"
    :height="340"
    :compact="{ below: 440, width: 358, height: 380 }"
    :initial="initial"
    :poster="poster"
    :script="script"
    :keys="{ wide: 'bottom-left', compact: 'bottom-left' }"
    :cursor="{ at: { at: 'doc', x: 0.3, y: 0.6 } }"
    class="sh"
    v-slot="{ state: s, rect, layout }"
  >
    <Window
      class="sh-window"
      :style="{
        left: `${GEO[layout].win.x}px`,
        top: `${GEO[layout].win.y}px`,
        width: `${GEO[layout].win.w}px`,
        height: `${GEO[layout].win.h}px`,
      }"
      :body="{ className: 'sh-body', 'data-crop': true }"
    >
      <template #lead>
        <span class="sh-lead">
          <FileText :size="15" :stroke-width="1.75" />
          <span>{{ DOC }}</span>
        </span>
      </template>
      <template #toolbar>
        <span class="sh-tools">
          <Facepile :names="['Maya Chen', 'Leo Park']" :size="22" :overlap="3" />
          <span class="sh-share" data-target="share" data-cursor="pointer" :data-on="s.open || undefined">
            <Lock :size="12" :stroke-width="2.25" />
            Share
          </span>
        </span>
      </template>
      <div class="sh-doc" data-target="doc">
        <Bar :w="180" :h="12" :tone="3" class="sh-doc__title" />
        <Bar :w="300" :h="7" :tone="2" />
        <Bar :w="340" :h="7" :tone="2" />
        <Bar :w="250" :h="7" :tone="2" />
        <span class="sh-doc__gap" />
        <Bar :w="320" :h="7" :tone="2" />
        <Bar :w="280" :h="7" :tone="2" />
      </div>
    </Window>

    <Popover :show="s.open" origin="top right" class="sh-pop" :style="popStyle(rect, layout)">
      <div class="sh-pop__head">
        <Text class="sh-pop__title">{{ `Share “${DOC}”` }}</Text>
      </div>
      <div class="sh-invite">
        <Field
          class="sh-field"
          :value="s.email"
          :chip="s.chip"
          :focused="s.open && !s.added && !s.menu"
          :placeholder="layout === 'wide' ? 'Add people by email' : 'Add by email'"
          :box="{ 'data-target': 'field' }"
        >
          <template #trailing>
            <span class="sh-role">
              <span class="sh-role__hit" data-target="role" data-cursor="pointer" :data-on="s.menu || undefined">
                <Roll variant="fade" align="end">{{ s.role }}</Roll>
                <ChevronDown :size="12" :stroke-width="2.25" />
              </span>
            </span>
          </template>
        </Field>
        <span class="sh-invite__btn" data-target="invite" data-cursor="pointer" :data-ready="s.chip || undefined">
          Invite
        </span>
      </div>
      <div class="sh-access">
        <div class="sh-access__label">People with access</div>
        <div class="sh-people">
          <Collapse :open="s.added" reveal="drop">
            <Row class="sh-person" :pad="6" title="Priya Shah" :subtitle="EMAIL">
              <template #lead>
                <Avatar name="Priya Shah" :size="28" />
              </template>
              <template #meta>
                <span class="sh-person__role">Can edit</span>
              </template>
            </Row>
          </Collapse>
          <Row class="sh-person" :pad="6" title="Maya Chen" subtitle="maya@lumen.co">
            <template #lead>
              <Avatar name="Maya Chen" :size="28" />
            </template>
            <template #meta>
              <span class="sh-person__role">Owner</span>
            </template>
          </Row>
          <Row class="sh-person" :pad="6" title="Leo Park" subtitle="leo@lumen.co">
            <template #lead>
              <Avatar name="Leo Park" :size="28" />
            </template>
            <template #meta>
              <span class="sh-person__role">Can view</span>
            </template>
          </Row>
        </div>
      </div>
      <Popover :show="s.menu" origin="top left" class="sh-menu" :style="roleMenu(rect, layout)">
        <Menu :items="roleItems(s.role)" :targets="ROLE_TARGETS" />
      </Popover>
    </Popover>
  </Stage>
</template>
