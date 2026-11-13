<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { Avatar, Badge, Bar, BrandMark, Icon, Meter, Connector, Count, Stage, States, Text, Window, useReducedMotion } from '../../kit'
import type { Act, Rect } from '../../kit'
import { figma, notion, slack } from '../../assets/app-icons'
import './bento.css'

// The bar for a bento grid (references/bento.md): the features section of
// Kite, a spend management app for small teams. Five tiles, hero and strip.
//
// The tile list, written before any tile was built:
//
//   Tile          Span   Kind        The one thing                    Moves
//   Receipts      2 × 1  Hero UI     a receipt lands on its charge    the receipt drops in, Missing turns Matched
//   Close         1 × 1  Stat        "2 days", on the one dark tile   counts down from 9
//   Cards         1 × 1  Object      the card itself                  rises out of the crop
//   Approvals     1 × 1  Component   one request, Approve             the button presses and turns Approved
//   Coding        1 × 1  Diagram     three merchants, one account     the lines draw in
//
// One window in the whole grid (the hero's). Every neighbor is a different
// kind, across and down. Each picture is its own Stage at 1:1, pinned to its
// tile's bottom and cropped by the tile; the copy is page text beside it.
// Each tile plays one beat, once, as it scrolls in, 110ms after the tile
// before it in reading order.

const STEP = 110
const LEAD = 450

type Beat = { on: boolean }
const before: Beat = { on: false }
const after: Beat = { on: true }
const beat = (i: number) => async (a: Act<Beat>) => {
  await a.wait(LEAD + i * STEP)
  await a.set({ on: true })
}

/* ---------------- Receipts (hero) ---------------- */

const ROWS = [
  { name: 74, who: 'A', amount: 44 },
  { real: true },
  { name: 58, who: 'J', amount: 38 },
  { name: 86, who: 'M', amount: 50 },
  { name: 64, who: 'A', amount: 42 },
]

// The tile owns the crop. Match its current width so an inner Stage never
// slices a window before the tile edge or shifts its content off the copy gutter.
function usePictureWidth() {
  const elRef = ref<HTMLDivElement | null>(null)
  const width = ref(340)
  let observer: ResizeObserver | null = null
  onMounted(() => {
    const node = elRef.value
    if (!node) return
    const measure = () => {
      width.value = Math.max(1, node.getBoundingClientRect().width)
    }
    measure()
    observer = new ResizeObserver(measure)
    observer.observe(node)
  })
  onBeforeUnmount(() => {
    observer?.disconnect()
  })
  return [elRef, width] as const
}

// Type, not a picture: page text in the tile, with one number that counts
// down once as the grid scrolls in.
function useInView<T extends Element>(delay: number) {
  const elRef = ref<T | null>(null)
  const seen = ref(false)
  let io: IntersectionObserver | null = null
  let t = 0
  onMounted(() => {
    const el = elRef.value
    if (!el) return
    io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return
        io?.disconnect()
        t = window.setTimeout(() => {
          seen.value = true
        }, delay)
      },
      { threshold: 0.4 },
    )
    io.observe(el)
  })
  onBeforeUnmount(() => {
    io?.disconnect()
    clearTimeout(t)
  })
  return [elRef, seen] as const
}

const [heroPicRef, heroWidth] = usePictureWidth()
const [approvePicRef, approveWidth] = usePictureWidth()
const [codePicRef, codeWidth] = usePictureWidth()

const reduced = useReducedMotion()
const [statRef, statSeen] = useInView<HTMLDivElement>(LEAD + STEP)

const goldId = useId()

// Real app icons, from the apps themselves (assets/app-icons.ts)
const MERCHANTS = [
  { name: 'Figma', icon: figma },
  { name: 'Slack', icon: slack },
  { name: 'Notion', icon: notion },
]

const right = (r: Rect) => ({ x: r.x + r.width, y: r.y + r.height / 2 })
const left = (r: Rect) => ({ x: r.x, y: r.y + r.height / 2 })
</script>

<template>
  <div class="kite-bento">
    <div class="kb-grid">
      <!-- Receipts (hero) -->
      <section class="kb-tile kb-tile--hero" data-crop>
        <p class="kb-copy">
          <b>Every receipt, matched.</b> Snap it or forward it, and Kite finds the charge it belongs to.
        </p>
        <div ref="heroPicRef" class="kb-picture kb-picture--hero">
          <Stage
            :width="heroWidth"
            :height="heroWidth < 600 ? 300 : 286"
            :initial="before"
            :poster="after"
            play="once"
            :script="beat(0)"
            class="kb-stage"
            v-slot="{ state: s }"
          >
            <Window
              v-if="heroWidth < 600"
              title="Transactions"
              class="kb-window kb-window--compact"
              :body="{ 'data-crop': '' }"
            >
              <div class="kb-ledger">
                <template v-for="(row, i) in ROWS" :key="i">
                  <div v-if="row.real" class="kb-row" data-real>
                    <BrandMark name="Blue Bottle" :size="26" />
                    <Text class="kb-row-name">Blue Bottle</Text>
                    <span class="kb-slot" :data-on="s.on || undefined">
                      <span class="kb-receipt" aria-hidden="true">
                        <Bar :w="14" :h="3" :r="1.5" :tone="4" />
                        <Bar :w="18" :h="2" :r="1" :tone="3" />
                        <Bar :w="12" :h="2" :r="1" :tone="3" />
                        <Bar :w="16" :h="2" :r="1" :tone="3" />
                      </span>
                      <States
                        :value="s.on ? 'matched' : 'missing'"
                        align="end"
                        class="kb-status"
                      >
                        <template #missing>
                          <Badge tone="warning" class="kb-pill">No receipt</Badge>
                        </template>
                        <template #matched>
                          <Badge tone="success" class="kb-pill">
                            <template #icon><Icon name="check" :size="12" /></template>
                            Matched
                          </Badge>
                        </template>
                      </States>
                    </span>
                    <Text class="kb-row-amount">$18.40</Text>
                    <span class="kb-row-rest">
                      <Avatar name="Mara" :size="20" />
                      <Bar :w="64" :h="6" :tone="2" />
                    </span>
                  </div>
                  <div v-else class="kb-row">
                    <Bar :w="26" :h="26" :r="7" :tone="2" />
                    <Bar :w="row.name!" :h="6" :tone="3" />
                    <span class="kb-slot">
                      <Bar :w="22" :h="28" :r="4" :tone="1" />
                      <Bar :w="62" :h="22" :r="11" :tone="1" />
                    </span>
                    <Bar :w="row.amount!" :h="6" :tone="3" class="kb-row-amount" />
                    <span class="kb-row-rest">
                      <Bar :w="20" :h="20" :r="10" :tone="2" />
                      <Bar :w="56 + ((i * 13) % 20)" :h="6" :tone="2" />
                    </span>
                  </div>
                </template>
              </div>
            </Window>

            <Window
              v-else
              class="kb-window"
              :body="{ 'data-crop': '' }"
              title="Transactions"
              :sidebar-width="156"
            >
              <template #toolbar>
                <span class="kb-tools">
                  <Bar :w="54" :h="24" :r="7" :tone="2" />
                  <Bar :w="24" :h="24" :r="7" :tone="2" />
                </span>
              </template>
              <template #sidebar>
                <nav class="kb-side">
                  <span class="kb-logo" aria-hidden="true">
                    <svg viewBox="0 0 16 16" width="12" height="12">
                      <path d="M8 1.5 13 7 8 14.5 3 7Z" fill="currentColor" />
                    </svg>
                  </span>
                  <span
                    v-for="(w, i) in [52, 70, 44, 58]"
                    :key="i"
                    class="kb-nav"
                    :data-active="i === 1 || undefined"
                  >
                    <Bar :w="12" :h="12" :r="3" :tone="i === 1 ? 4 : 2" />
                    <Bar :w="w" :h="6" :tone="i === 1 ? 4 : 2" />
                  </span>
                </nav>
              </template>
              <div class="kb-ledger">
                <template v-for="(row, i) in ROWS" :key="i">
                  <div v-if="row.real" class="kb-row" data-real>
                    <BrandMark name="Blue Bottle" :size="26" />
                    <Text class="kb-row-name">Blue Bottle</Text>
                    <span class="kb-slot" :data-on="s.on || undefined">
                      <span class="kb-receipt" aria-hidden="true">
                        <Bar :w="14" :h="3" :r="1.5" :tone="4" />
                        <Bar :w="18" :h="2" :r="1" :tone="3" />
                        <Bar :w="12" :h="2" :r="1" :tone="3" />
                        <Bar :w="16" :h="2" :r="1" :tone="3" />
                      </span>
                      <States
                        :value="s.on ? 'matched' : 'missing'"
                        align="start"
                        class="kb-status"
                      >
                        <template #missing>
                          <Badge tone="warning" class="kb-pill">No receipt</Badge>
                        </template>
                        <template #matched>
                          <Badge tone="success" class="kb-pill">
                            <template #icon><Icon name="check" :size="12" /></template>
                            Matched
                          </Badge>
                        </template>
                      </States>
                    </span>
                    <Text class="kb-row-amount">$18.40</Text>
                    <span class="kb-row-rest">
                      <Avatar name="Mara" :size="20" />
                      <Bar :w="64" :h="6" :tone="2" />
                    </span>
                  </div>
                  <div v-else class="kb-row">
                    <Bar :w="26" :h="26" :r="7" :tone="2" />
                    <Bar :w="row.name!" :h="6" :tone="3" />
                    <span class="kb-slot">
                      <Bar :w="22" :h="28" :r="4" :tone="1" />
                      <Bar :w="62" :h="22" :r="11" :tone="1" />
                    </span>
                    <Bar :w="row.amount!" :h="6" :tone="3" class="kb-row-amount" />
                    <span class="kb-row-rest">
                      <Bar :w="20" :h="20" :r="10" :tone="2" />
                      <Bar :w="56 + ((i * 13) % 20)" :h="6" :tone="2" />
                    </span>
                  </div>
                </template>
              </div>
            </Window>
          </Stage>
        </div>
      </section>

      <!-- Close (stat) -->
      <section class="kb-tile kb-tile--stat" data-dark data-crop>
        <div ref="statRef" class="kb-stat">
          <span class="kb-stat-lead">Month-end close in</span>
          <span class="kb-stat-number">
            <Count :value="statSeen || reduced ? 2 : 9" :duration="1100" />
            <span class="kb-stat-unit"> days</span>
          </span>
          <span class="kb-stat-label">down from nine for the average team in its first quarter.</span>
        </div>
      </section>

      <!-- Cards (object) -->
      <section class="kb-tile kb-tile--card" data-crop>
        <p class="kb-copy">
          <b>A card for everyone.</b> Each with its own limit. No more reimbursements.
        </p>
        <div class="kb-picture kb-picture--small">
          <Stage
            :width="360"
            :height="206"
            :initial="before"
            :poster="after"
            play="once"
            :script="beat(2)"
            class="kb-stage"
            v-slot="{ state: s }"
          >
            <div class="kb-card" :data-on="s.on || undefined">
              <span class="kb-card-mark">
                <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
                  <path d="M8 1.5 13 7 8 14.5 3 7Z" fill="currentColor" />
                </svg>
                Kite
              </span>
              <svg class="kb-card-chip" viewBox="0 0 34 26" width="34" height="26" aria-hidden="true">
                <defs>
                  <linearGradient :id="goldId" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stop-color="#f3e2b0" />
                    <stop offset="0.5" stop-color="#d9bc78" />
                    <stop offset="1" stop-color="#b8954f" />
                  </linearGradient>
                </defs>
                <rect x="0.5" y="0.5" width="33" height="25" rx="4.5" :fill="`url(#${goldId})`" stroke="#8f733a" stroke-opacity="0.6" />
                <g fill="none" stroke="#8f733a" stroke-opacity="0.75" stroke-width="0.8">
                  <path d="M0.5 9H11.5M0.5 17H11.5M22.5 9H33.5M22.5 17H33.5" />
                  <rect x="11.5" y="5.5" width="11" height="15" rx="2.5" />
                </g>
              </svg>
              <span class="kb-card-name">Maya Chen</span>
              <span class="kb-card-last">•••• 2207</span>
            </div>
          </Stage>
        </div>
      </section>

      <!-- Approvals (component) -->
      <section class="kb-tile kb-tile--approve" data-crop>
        <p class="kb-copy">
          <b>Approve in one tap.</b> Requests go straight to whoever owns the budget.
        </p>
        <div ref="approvePicRef" class="kb-picture kb-picture--aligned">
          <Stage
            :width="approveWidth"
            :height="206"
            :initial="before"
            :poster="after"
            play="once"
            :script="beat(3)"
            class="kb-stage"
            v-slot="{ state: s }"
          >
            <div class="kb-request">
              <div class="kb-request-who">
                <Avatar name="Jon" :size="36" tone="accent" />
                <span class="kb-request-text">
                  <Text class="kb-request-name">Jon Park</Text>
                  <Text class="kb-request-what">Figma, 3 seats</Text>
                </span>
                <Text class="kb-request-amount">$45</Text>
              </div>
              <div class="kb-request-actions">
                <span class="kb-btn">Decline</span>
                <span class="kb-btn kb-btn--primary" :data-on="s.on || undefined">
                  <States :value="s.on ? 'done' : 'ask'" :states="{ ask: 'Approve' }">
                    <template #done>
                      <Icon name="check" :size="14" /> Approved
                    </template>
                  </States>
                </span>
              </div>
              <div class="kb-request-budget">
                <Bar :w="86" :h="6" :tone="3" />
                <Meter :value="0.62" class="kb-meter" />
              </div>
            </div>
          </Stage>
        </div>
      </section>

      <!-- Coding (diagram) -->
      <section class="kb-tile kb-tile--code" data-crop>
        <p class="kb-copy">
          <b>Coded as it happens.</b> Every charge lands in the right account, no spreadsheet.
        </p>
        <div ref="codePicRef" class="kb-picture kb-picture--aligned">
          <Stage
            :width="codeWidth"
            :height="206"
            :initial="before"
            :poster="after"
            play="once"
            :script="beat(4)"
            class="kb-stage"
            v-slot="{ state: s, rect }"
          >
            <div class="kb-merchants">
              <span v-for="m in MERCHANTS" :key="m.name" class="kb-merchant" :data-target="`m-${m.name}`">
                <img class="kb-merchant-icon" :src="m.icon" alt="" />
                <Text>{{ m.name }}</Text>
              </span>
            </div>
            <span class="kb-account" data-target="account" :data-on="s.on || undefined">
              <span class="kb-account-code">6100</span>
              <Text>Software</Text>
            </span>
            <template v-for="(m, i) in MERCHANTS" :key="m.name">
              <Connector
                v-if="rect('account') && rect(`m-${m.name}`)"
                :from="right(rect(`m-${m.name}`))"
                :to="left(rect('account'))"
                route="step"
                :show="s.on"
                :class="`kb-line kb-line--${i}`"
              />
            </template>
          </Stage>
        </div>
      </section>
    </div>
  </div>
</template>
