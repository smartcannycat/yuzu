<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  AtSign,
  Bell,
  Bookmark,
  ChevronDown,
  CircleHelp,
  Clock,
  Ellipsis,
  EllipsisVertical,
  Forward,
  Hash,
  Headphones,
  House,
  MessageSquareText,
  MessagesSquare,
  Mic,
  Plus,
  Search,
  SendHorizontal,
  Smile,
  SmilePlus,
  SquarePen,
  Type,
  X,
} from 'lucide-vue-next'
import { defineComponent, h, type Component, type PropType } from 'vue'
import { Bar, Collapse, Stage, Text, Window, type Act } from '../../kit'
import './slack.css'

// Slack, in #design. Maya's message arrives, the user hovers it and taps 👀
// from the quick reactions, opens the thread and replies. Closing the thread
// leaves the reaction and reply summary in place until the host's Replay.
//
// Icons: Slack's own set isn't available, so Lucide is used on purpose: its
// rounded 1.75 stroke is the closest match to Slack's outline glyphs.

type S = {
  arrived: boolean
  reacted: boolean
  thread: boolean
  focus: boolean
  typing: boolean
  draft: string
  replied: boolean
}

const initial: S = { arrived: true, reacted: false, thread: false, focus: false, typing: false, draft: '', replied: false }

// Under reduced motion: the finished moment, reacted and replied in the open thread
const poster: S = { ...initial, arrived: true, reacted: true, thread: true, replied: true }

const MESSAGE = 'The new onboarding flow is ready for review. Can you take a look before standup?'
const REPLY = "On it, I'll leave notes in the file"
const REST = { x: 560, y: 250 }

async function script(a: Act<S>) {
  // Opens on the channel with Maya's message already in.
  await a.wait(1200)

  // Hover the message: the row lights up and its toolbar shows
  a.mark('hover')
  await a.move({ at: 'msg', x: 0.42, y: 0.55 })
  await a.wait(500)

  // 👀 from the quick reactions
  await a.move({ at: 'react-eyes', x: 0.82, y: 0.86 })
  await a.wait(220)
  a.mark('react')
  await a.click()
  await a.set({ reacted: true })
  await a.wait(1000)

  // Reply in thread
  await a.move({ at: 'reply-btn', x: 0.78, y: 0.82 })
  await a.wait(260)
  a.mark('thread')
  await a.click()
  await a.set({ thread: true })
  await a.wait(800)

  // Write the reply
  await a.move({ at: 'tbox', x: 0.62, y: 0.3 })
  await a.click()
  await a.set({ focus: true })
  await a.wait(350)
  await a.set({ typing: true })
  await a.type('draft', REPLY, { interval: 52 })
  await a.set({ typing: false })
  await a.wait(450)
  a.mark('send')
  await a.key('enter')
  await a.set({ draft: '', replied: true })
  await a.wait(500)
  // Step off the reply as it lands, so the pointer isn't parked on its words
  const box = a.rect('tbox')
  await a.move({ x: box.x + box.width * 0.7, y: box.y + box.height + 60 })
  await a.wait(1800)

  // Close the thread and hold the result. Replay is the explicit reset.
  a.mark('exit')
  await a.move({ at: 'tclose', x: 0.5, y: 0.5 })
  await a.wait(200)
  await a.click()
  await a.set({ thread: false, focus: false })
  await a.wait(500)
  await a.move(REST)
  await a.wait(1500)
  a.mark('done')
}

type Who = 'maya' | 'alex' | 'p1' | 'p2' | 'p3'
const LETTERS: Record<Who, string> = { maya: 'M', alex: 'A', p1: 'J', p2: 'R', p3: 'T' }

const Face = defineComponent({
  props: {
    who: { type: String as PropType<Who>, required: true },
    size: { type: Number, default: 36 },
  },
  setup(props) {
    return () =>
      h(
        'span',
        {
          class: 'sl-face',
          'data-who': props.who,
          style: {
            width: `${props.size}px`,
            height: `${props.size}px`,
            fontSize: `${Math.round(props.size * 0.42)}px`,
            borderRadius: `${Math.round(props.size * 0.22)}px`,
          },
        },
        LETTERS[props.who],
      )
  },
})

const SideBar = defineComponent({
  props: {
    w: { type: Number, required: true },
    light: { type: Boolean, default: false },
  },
  setup(props) {
    return () => h(Bar, { w: props.w, h: 6, style: { background: props.light ? '#b192b3' : '#8c6a8e' } })
  },
})

const RAIL_ITEMS: { icon: Component; label: string; active?: boolean }[] = [
  { icon: House, label: 'Home', active: true },
  { icon: MessagesSquare, label: 'DMs' },
  { icon: Bell, label: 'Activity' },
  { icon: Ellipsis, label: 'More' },
]

const DMS: Who[] = ['p1', 'maya', 'p3']
const DM_WIDTHS = [54, 66, 48]
const QUICK_EMOJIS = ['✅', '👀', '🙌']
</script>

<template>
  <Stage
    :width="940"
    :height="540"
    :compact="{ below: 600, width: 440, height: 440 }"
    :initial="initial"
    :poster="poster"
    :script="script"
    play="once"
    :cursor="{ at: REST }"
    class="sl"
    keys="bottom"
    v-slot="{ state: s }"
  >
    <Window class="sl-win">
      <template #lead>
        <span class="sl-top__nav">
          <ArrowLeft :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
          <ArrowRight :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
          <Clock :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
        </span>
        <span class="sl-top__search">
          <Search :size="13" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
          <Text>Search Northwind</Text>
        </span>
      </template>

      <template #toolbar>
        <span class="sl-top__help">
          <CircleHelp :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
        </span>
      </template>

      <div class="sl-body">
        <!-- Rail -->
        <nav class="sl-rail">
          <span class="sl-rail__ws">N</span>
          <span
            v-for="it in RAIL_ITEMS"
            :key="it.label"
            class="sl-rail__item"
            :data-active="it.active || undefined"
          >
            <span class="sl-rail__btn">
              <component :is="it.icon" :size="18" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
            </span>
            <Text class="sl-rail__label">{{ it.label }}</Text>
          </span>
          <span class="sl-grow" />
          <span class="sl-rail__plus">
            <Plus :size="16" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
          </span>
          <span class="sl-rail__me">
            <Face who="alex" :size="32" />
            <span class="sl-rail__status" />
          </span>
        </nav>

        <div class="sl-panel">
          <!-- Sidebar -->
          <aside class="sl-side">
            <div class="sl-side__head">
              <Text class="sl-side__ws">Northwind</Text>
              <ChevronDown :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
              <span class="sl-grow" />
              <span class="sl-side__compose">
                <SquarePen :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
              </span>
            </div>
            <div class="sl-side__list">
              <div v-for="(w, i) in [46, 58]" :key="i" class="sl-side__row">
                <span class="sl-side__glyph" />
                <SideBar :w="w" />
              </div>
              <div class="sl-side__section">
                <ChevronDown :size="12" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                <SideBar :w="52" light />
              </div>
              <div class="sl-side__row">
                <Hash :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                <SideBar :w="44" />
              </div>
              <div class="sl-side__row" data-active>
                <Hash :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                <Text class="sl-side__name">design</Text>
              </div>
              <div v-for="(w, i) in [60, 38]" :key="`ch-${i}`" class="sl-side__row">
                <Hash :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                <SideBar :w="w" />
              </div>
              <div class="sl-side__section">
                <ChevronDown :size="12" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                <SideBar :w="74" light />
              </div>
              <div v-for="(who, i) in DMS" :key="who" class="sl-side__row">
                <Face :who="who" :size="18" />
                <SideBar :w="DM_WIDTHS[i]" />
              </div>
            </div>
          </aside>

          <!-- Channel -->
          <section class="sl-channel" :data-thread="s.thread || undefined">
            <header class="sl-channel__head">
              <span class="sl-channel__title">
                <Hash :size="16" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                <Text>design</Text>
                <ChevronDown :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
              </span>
              <span class="sl-grow" />
              <span class="sl-members">
                <span class="sl-members__faces">
                  <Face who="p1" :size="20" />
                  <Face who="maya" :size="20" />
                  <Face who="p2" :size="20" />
                </span>
                <span class="sl-members__count">12</span>
              </span>
              <span class="sl-headbtn">
                <Headphones :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
              </span>
            </header>
            <div class="sl-tabs">
              <span class="sl-tab" data-active>
                <MessageSquareText :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                <Text>Messages</Text>
              </span>
              <span class="sl-tab">
                <span class="sl-tab__glyph" />
                <Bar :w="40" :h="6" :tone="2" />
              </span>
              <span class="sl-tab sl-tab--plus">
                <Plus :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
              </span>
            </div>

            <div class="sl-feed" data-crop>
              <div class="sl-divider">
                <span class="sl-divider__pill">
                  <Bar :w="46" :h="6" :tone="3" />
                </span>
              </div>
              <!-- Older messages -->
              <div class="sl-msg">
                <Face who="p1" />
                <div class="sl-msg__body">
                  <div class="sl-msg__meta sl-msg__meta--bars">
                    <Bar :w="74" :h="7" :tone="4" />
                    <Bar :w="34" :h="5" :tone="2" />
                  </div>
                  <div class="sl-msg__lines">
                    <Bar :w="196" :h="6" :tone="2" />
                  </div>
                </div>
              </div>
              <div class="sl-msg">
                <Face who="p2" />
                <div class="sl-msg__body">
                  <div class="sl-msg__meta sl-msg__meta--bars">
                    <Bar :w="58" :h="7" :tone="4" />
                    <Bar :w="34" :h="5" :tone="2" />
                  </div>
                  <div class="sl-msg__lines">
                    <Bar :w="142" :h="6" :tone="2" />
                  </div>
                </div>
              </div>

              <Collapse :open="s.arrived" class="sl-live">
                <div class="sl-row" data-target="msg">
                  <div class="sl-msg sl-msg--live">
                    <Face who="maya" />
                    <div class="sl-msg__body">
                      <div class="sl-msg__meta">
                        <Text class="sl-msg__name">Maya Chen</Text>
                        <Text class="sl-msg__time">10:42 AM</Text>
                      </div>
                      <p class="sl-msg__text">{{ MESSAGE }}</p>
                      <Collapse :open="s.reacted">
                        <div class="sl-msg__reacts">
                          <span class="sl-react" data-mine="true">
                            <span class="sl-react__emoji">👀</span>
                            <span class="sl-react__count">1</span>
                          </span>
                        </div>
                      </Collapse>
                      <Collapse :open="s.replied">
                        <div class="sl-replies">
                          <Face who="alex" :size="20" />
                          <Text class="sl-replies__link">1 reply</Text>
                          <Text class="sl-replies__when">Last reply just now</Text>
                        </div>
                      </Collapse>
                    </div>
                  </div>
                  <!-- HoverBar -->
                  <div class="sl-hover">
                    <span
                      v-for="e in QUICK_EMOJIS"
                      :key="e"
                      class="sl-hover__btn sl-hover__emoji"
                      :data-target="e === '👀' ? 'react-eyes' : undefined"
                    >
                      {{ e }}
                    </span>
                    <span class="sl-hover__div" />
                    <span class="sl-hover__btn">
                      <SmilePlus :size="16" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                    </span>
                    <span class="sl-hover__btn" data-target="reply-btn">
                      <MessageSquareText :size="16" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                    </span>
                    <span class="sl-hover__btn">
                      <Forward :size="16" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                    </span>
                    <span class="sl-hover__btn">
                      <Bookmark :size="16" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                    </span>
                    <span class="sl-hover__btn">
                      <EllipsisVertical :size="16" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                    </span>
                  </div>
                </div>
              </Collapse>
            </div>

            <div class="sl-channel__compose">
              <div class="sl-compose">
                <div class="sl-compose__text">
                  <span class="sl-compose__placeholder">Message #design</span>
                  <span class="sl-compose__draft" />
                  <span class="sl-caret" />
                </div>
                <div class="sl-compose__tools">
                  <span class="sl-compose__round">
                    <Plus :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                  </span>
                  <Type :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                  <Smile :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                  <AtSign :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                  <span class="sl-compose__sep" />
                  <Mic :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                  <span class="sl-grow" />
                  <span class="sl-compose__send">
                    <SendHorizontal :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                  </span>
                </div>
              </div>
            </div>
          </section>

          <!-- Thread -->
          <div class="sl-thread-wrap" :data-open="s.thread || undefined" data-crop>
            <aside class="sl-thread">
              <header class="sl-thread__head">
                <Text class="sl-thread__title">Thread</Text>
                <span class="sl-thread__where">
                  <Hash :size="12" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                  <Text>design</Text>
                </span>
                <span class="sl-grow" />
                <span class="sl-headbtn" data-target="tclose">
                  <X :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                </span>
              </header>
              <div class="sl-thread__body">
                <div class="sl-msg sl-msg--thread">
                  <Face who="maya" />
                  <div class="sl-msg__body">
                    <div class="sl-msg__meta">
                      <Text class="sl-msg__name">Maya Chen</Text>
                      <Text class="sl-msg__time">10:42 AM</Text>
                    </div>
                    <p class="sl-msg__text">{{ MESSAGE }}</p>
                    <div class="sl-msg__reacts">
                      <span class="sl-react" data-mine="true">
                        <span class="sl-react__emoji">👀</span>
                        <span class="sl-react__count">1</span>
                      </span>
                    </div>
                  </div>
                </div>
                <Collapse :open="s.replied">
                  <div class="sl-thread__count">
                    <Text>1 reply</Text>
                    <span class="sl-thread__rule" />
                  </div>
                  <div class="sl-msg sl-msg--thread">
                    <Face who="alex" />
                    <div class="sl-msg__body">
                      <div class="sl-msg__meta">
                        <Text class="sl-msg__name">Alex Rivera</Text>
                        <Text class="sl-msg__time">10:43 AM</Text>
                      </div>
                      <p class="sl-msg__text">{{ REPLY }}</p>
                    </div>
                  </div>
                </Collapse>
                <div class="sl-thread__compose">
                  <div
                    class="sl-compose"
                    :data-focus="s.focus || undefined"
                    data-target="tbox"
                    data-cursor="ibeam"
                  >
                    <div class="sl-compose__text">
                      <span class="sl-compose__placeholder" :data-hide="s.draft.length > 0 || undefined">
                        Reply…
                      </span>
                      <span class="sl-compose__draft">{{ s.draft }}</span>
                      <span class="sl-caret" :data-show="s.focus || undefined" :data-typing="s.typing || undefined" />
                    </div>
                    <div class="sl-compose__tools">
                      <span class="sl-compose__round">
                        <Plus :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                      </span>
                      <Type :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                      <Smile :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                      <AtSign :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                      <span class="sl-compose__sep" />
                      <Mic :size="15" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                      <span class="sl-grow" />
                      <span class="sl-compose__send" :data-ready="s.draft.length > 0 || undefined">
                        <SendHorizontal :size="14" :stroke-width="1.75" class="sl-i" aria-hidden="true" />
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </Window>
  </Stage>
</template>
