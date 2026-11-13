<script setup lang="ts">
import { Stage, Phone, Thread, Bubble, Stamp, Receipt, type Act, Avatar } from '../../kit'
import './messages.css'

// A conversation at true iOS size: your reply is typed into the composer and
// sent, the bubble forming out of the field's words; the receipt turns to
// Read, they start typing, and the dots grow into their reply. The new
// conversation holds once complete; the host can explicitly replay it.

type S = { draft: string; sent: boolean; delivered: boolean; read: boolean; typing: boolean; reply: boolean }
const initial: S = { draft: '', sent: false, delivered: false, read: false, typing: false, reply: false }
// Reduced motion shows the whole exchange
const poster: S = { ...initial, sent: true, delivered: true, read: true, reply: true }
const MINE = 'Yes! See you at 7'

async function script(a: Act<S>) {
  await a.wait(700)
  await a.click('compose')
  await a.type('draft', MINE, { interval: 60 })
  await a.wait(450)
  await a.click('send')
  // Clear the field in the same update that adds the bubble: the words lift out of it
  await a.set({ sent: true, draft: '' })
  await a.wait(600)
  await a.set({ delivered: true })
  await a.wait(900)
  await a.set({ read: true })
  await a.wait(700)
  await a.set({ typing: true })
  await a.wait(1600)
  await a.set({ typing: false, reply: true })
  await a.wait(2600)
}
</script>

<template>
  <Stage
    :width="420"
    :height="340"
    :compact="{ below: 420, width: 358, height: 340 }"
    :initial="initial"
    :poster="poster"
    :script="script"
    play="once"
    :cursor="{ at: 'compose', style: 'touch' }"
    class="ms"
    v-slot="{ state: s }"
  >
    <Phone :width="326" class="ms-phone">
      <div class="ms-head">
        <Avatar name="Maya" tone="ios" :size="52" class="ms-avatar" />
        <span class="ms-name">Maya</span>
      </div>
      <Thread class="ms-thread">
        <Stamp>Today 9:38</Stamp>
        <Bubble from="them">Are we still on for tonight?</Bubble>
        <Bubble from="them">I booked the place on 5th</Bubble>
        <Bubble v-if="s.sent" from="me" source="draft">
          {{ MINE }}
        </Bubble>
        <Receipt :show="s.delivered">{{ s.read ? 'Read 9:41' : 'Delivered' }}</Receipt>
        <Bubble v-if="s.typing || s.reply" from="them" :typing="s.typing">
          Perfect, I'll grab us a table by the window
        </Bubble>
      </Thread>
      <div class="ms-compose">
        <span class="ms-plus" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 16 16">
            <path d="M8 2.5v11M2.5 8h11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </span>
        <span class="ms-field" data-target="compose">
          <span class="ms-field__text" data-target="draft">
            {{ s.draft }}<i v-if="s.draft" class="ms-caret" data-snap />
          </span>
          <span class="ms-field__ph" :data-hide="s.draft ? '' : undefined">
            iMessage
          </span>
          <span class="ms-send" data-target="send" :data-show="s.draft ? '' : undefined">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M8 13V3.5M3.5 7.5 8 3l4.5 4.5"
                fill="none"
                stroke="currentColor"
                stroke-width="2.4"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>
        </span>
      </div>
    </Phone>
  </Stage>
</template>
