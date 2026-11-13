<script setup lang="ts">
import { ArrowUp, ChevronLeft, Mic, Plus, Video } from 'lucide-vue-next'
import { Stage, Phone, Thread, Bubble, Stamp, Receipt, Keyboard, type Act, Avatar } from '../../kit'
import './imessage.css'

// iMessage on an iPhone, for a landing page. Four beats:
//   1. Context: Maya's two messages, keyboard up, the field focused.
//   2. Reply: the person types (keys pop as iOS keys do), taps send; the
//      bubble rises in, the receipt reads Delivered, then rolls to Read.
//   3. Maya types (the dots), and the dots grow into her reply. Her reply
//      makes the receipt redundant, so it folds away, as iOS does.
// Hold the completed conversation. Replay is the explicit reset; sent
// messages do not disappear from the live thread on their own.
//
// Real strings: Maya, the stamp, her two messages, the typed reply, the
// receipt, her reply. The keyboard keeps its letters: it is the domain's
// signature, not information.

type S = {
  draft: string
  keys: boolean
  sent: boolean
  delivered: boolean
  read: boolean
  typing: boolean
  reply: boolean
}

const initial: S = {
  draft: '',
  keys: false,
  sent: false,
  delivered: false,
  read: false,
  typing: false,
  reply: false,
}

const MINE = "No way, I'm so in"
const REPLY = "Leaving at 5, I'll drive"

// The predictive bar follows the word being typed, as iOS's does
const SUGGEST: Record<string, [string, string]> = {
  N: ['No', 'Not'],
  No: ['Now', 'Not'],
  w: ['was', 'we'],
  wa: ['way', 'was'],
  way: ['way', 'was'],
  'way,': ['I', 'I’m'],
  I: ['I’m', 'I'],
  "I'": ['I’m', 'I’ll'],
  "I'm": ['I’m', 'I’ve'],
  s: ['so', 'see'],
  so: ['so', 'soon'],
  i: ['in', 'is'],
  in: ['in', 'it'],
}

function suggestions(draft: string): [string, string, string] {
  const word = draft.split(' ').pop() ?? ''
  if (!word) return draft ? ['I', 'the', 'and'] : ['I', 'The', 'I’m']
  const [a, b] = SUGGEST[word] ?? [word, word]
  return [`“${word}”`, a, b]
}

async function script(a: Act<S>) {
  await a.wait(900)
  a.mark('type')
  await a.set({ keys: true })
  await a.type('draft', MINE, { interval: 95 })
  await a.wait(150)
  await a.set({ keys: false })
  await a.wait(250)
  a.mark('send')
  await a.click({ at: 'send', x: 0.5, y: 0.5 })
  await a.set({ sent: true, draft: '' })
  await a.wait(700)
  await a.set({ delivered: true })
  await a.wait(1200)
  await a.set({ read: true })
  await a.wait(900)
  a.mark('typing')
  await a.set({ typing: true })
  await a.wait(1900)
  await a.set({ typing: false, reply: true })
  await a.wait(3700)
  a.mark('done')
}
</script>

<template>
  <Stage
    :width="420"
    :height="620"
    :initial="initial"
    :poster="{ ...initial, sent: true, delivered: true, read: true, reply: true }"
    :script="script"
    play="once"
    :cursor="{ at: { x: 330, y: 420 }, style: 'touch' }"
    class="im"
    v-slot="{ state: s }"
  >
    <div class="im-wash" />
    <Phone :width="360" class="im-phone">
      <div class="im-app">
        <header class="im-head">
          <span class="im-back">
            <ChevronLeft :size="30" :stroke-width="2.4" />
          </span>
          <span class="im-contact">
            <Avatar name="Maya" tone="ios" :size="46" class="im-avatar" />
            <span class="im-name">
              Maya
              <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">
                <path d="M6 3.5 10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
          </span>
          <span class="im-video">
            <Video :size="26" :stroke-width="1.8" />
          </span>
        </header>

        <Thread class="im-thread">
          <Bubble from="them">Did you see the lake house?</Bubble>
          <Bubble from="me">Any luck finding a place?</Bubble>
          <Stamp>
            <b>Today</b> 9:38
          </Stamp>
          <Bubble from="them">Booked the cabin for Friday!</Bubble>
          <Bubble from="them">Hot tub and a lake view</Bubble>
          <Bubble v-if="s.sent" from="me" source=".im-field__text">
            {{ MINE }}
          </Bubble>
          <Receipt v-if="s.sent" :show="s.delivered" class="im-receipt">
            {{ s.read ? 'Read 9:41' : 'Delivered' }}
          </Receipt>
          <Bubble
            v-if="s.typing || s.reply"
            from="them"
            :typing="s.typing"
          >
            {{ REPLY }}
          </Bubble>
        </Thread>

        <div class="im-compose">
          <span class="im-plus">
            <Plus :size="20" :stroke-width="2.2" />
          </span>
          <span class="im-field">
            <span class="im-field__text">
              {{ s.draft }}<i class="im-caret" :data-solid="s.keys || undefined" /><span v-if="!s.draft" class="im-field__ph">iMessage</span>
            </span>
            <span class="im-mic" :data-off="!!s.draft || undefined">
              <Mic :size="19" :stroke-width="2" />
            </span>
            <span class="im-send" :data-on="!!s.draft || undefined" data-target="send">
              <ArrowUp :size="19" :stroke-width="3" />
            </span>
          </span>
        </div>

        <Keyboard :typed="s.draft" :suggestions="suggestions(s.draft)" />
      </div>
    </Phone>
  </Stage>
</template>
