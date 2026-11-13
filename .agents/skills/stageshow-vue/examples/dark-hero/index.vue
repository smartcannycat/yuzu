<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { GitBranch, GitCommitHorizontal } from 'lucide-vue-next'
import { Badge, Bar, Collapse, Spinner, Stage, Window, type Act } from '../../kit'
import './hero.css'

// A dark desktop hero: a deploy lands at the top of a project's deployments
// and goes live. Beats: the new deploy opens in at the top and pushes the
// list down, Building with a spinner; its timer counts; the badge turns to
// Ready on the same pill and the timer settles on the build's time; the
// row's Current mark moves to it. After a 2s hold the new row closes the
// way it opened, handing Current back, and resets while closed.
//
// What makes a dark hero read:
// - The window is a step lighter than the page, its chrome a step lighter
//   again, with a hairline on top, not a glow. Shadows don't show on black,
//   so depth comes from those steps.
// - One color is lit: the success green, once, on the new row. Everything
//   else is grays; the old rows' Ready pills are dimmed so the new one leads.
// - The status changes on one pill: the tone eases, the spinner and dot
//   crossfade in one cell, and the pill narrows to fit "Ready" from its
//   right edge only. The mark and the word never move; "Building" has faded
//   before the edge reaches it, so no letter is ever cut. No second pill.
// - The list moves by its height, so the old rows slide down as one, never
//   jump.
//
// Real strings: the project, the branch, the new commit, its status and time,
// and the row it replaced. The rest is placeholder at real line heights.

type S = { open: boolean; ready: boolean; t: number }

const initial: S = { open: false, ready: false, t: 0 }

async function script(a: Act<S>) {
  await a.wait(900)
  a.mark('deploy')
  a.put({ open: true })
  for (let t = 1; t <= 4; t++) {
    await a.wait(520)
    a.put({ t: t * 9 })
  }
  await a.wait(300)
  a.mark('ready')
  a.put({ ready: true, t: 38 })
  await a.wait(2000)
  // The list loses what the loop added in one motion; the closed row's
  // status and timer go back where nobody sees them
  a.put({ open: false })
  await a.wait(700)
  await a.snap({ ready: false, t: 0 })
}

const OLD = [
  { msg: 'Fix pricing copy', when: '2h ago', t: '41s' },
  { msg: null, when: null, t: null },
  { msg: null, when: null, t: null },
  { msg: null, when: null, t: null },
]

// The status word. The pill keeps its left edge and only its right edge
// moves: the cell eases to the width of the word that is showing. Getting
// shorter, the old word fades out before the edge reaches it; getting
// longer, the edge opens first and the new word fades into the room.
const words = ref<HTMLSpanElement[]>([])
const w = ref<number[]>([])
onMounted(() => {
  w.value = words.value.map((e) => e?.offsetWidth ?? 0)
})

function setWordRef(el: any, i: number) {
  if (el) words.value[i] = el as HTMLSpanElement
}
</script>

<template>
  <Stage
    :width="760"
    :height="440"
    :compact="{ below: 760, width: 358, height: 440 }"
    theme="dark"
    :initial="initial"
    :poster="{ open: true, ready: true, t: 38 }"
    :script="script"
    class="dh"
    v-slot="{ state: s, layout }"
  >
    <Window url="app.shipyard.dev/northwind/deployments" class="dh-win" :sidebar-width="168">
      <template v-if="layout !== 'compact'" #sidebar>
        <nav class="dh-side">
          <span v-for="(navW, i) in [64, 88, 52, 76, 60]" :key="i" class="dh-nav" :data-active="i === 1 || undefined">
            <Bar :w="12" :h="12" :r="3" :tone="i === 1 ? 4 : 2" />
            <Bar :w="navW" :h="6" :tone="i === 1 ? 4 : 2" />
          </span>
        </nav>
      </template>

      <div class="dh-body">
        <header class="dh-head">
          <div class="dh-title">Deployments</div>
          <span class="dh-proj">
            <Bar :w="14" :h="14" :r="4" :tone="3" />
            northwind-web
          </span>
        </header>
        <div class="dh-list">
          <Collapse :open="s.open" reveal="drop">
            <div class="dh-row" data-lead="true">
              <span class="dh-lines">
                <span class="dh-msg">
                  Add annual plans
                  <span class="dh-current" :data-on="s.ready || undefined">Current</span>
                </span>
                <!-- Each icon is held with its words, and the pairs sit a clear
                     gap apart, so no word runs into the next icon -->
                <span class="dh-meta">
                  <span class="dh-meta__item"><GitBranch :size="12" :stroke-width="2" />main</span>
                  <span class="dh-meta__item"><GitCommitHorizontal :size="12" :stroke-width="2" />a41c9e2</span>
                  <span class="dh-when">Just now</span>
                </span>
              </span>
              <Badge :tone="s.ready ? 'success' : 'neutral'" class="dh-badge">
                <template #icon>
                  <!-- The status mark: spinner and dot share one 8px cell and crossfade, so
                       the word beside it never moves; the cell is the spinner's own size, so
                       the pill's padding reads the same on both sides -->
                  <span class="dh-mark" :data-ready="s.ready || undefined">
                    <Spinner :size="8" />
                    <i class="dh-dot" />
                  </span>
                </template>
                <span
                  class="dh-label"
                  :data-shrink="(w.length === 2 && w[s.ready ? 1 : 0]! < w[1 - (s.ready ? 1 : 0)]!) || undefined"
                  :style="w.length ? { width: `${w[s.ready ? 1 : 0]}px` } : undefined"
                >
                  <span
                    v-for="(t, i) in ['Building', 'Ready']"
                    :key="t"
                    :ref="(el) => setWordRef(el, i)"
                    class="dh-word"
                    :data-on="i === (s.ready ? 1 : 0) || undefined"
                  >{{ t }}</span>
                </span>
              </Badge>
              <span class="dh-time">{{ `${s.t}s` }}</span>
            </div>
          </Collapse>

          <template v-for="(r, i) in OLD" :key="i">
            <div v-if="r.msg" class="dh-row">
              <span class="dh-lines">
                <span class="dh-msg">
                  {{ r.msg }}
                  <span class="dh-current" :data-on="!(s.open && s.ready) || undefined">Current</span>
                </span>
                <span class="dh-meta">
                  <span class="dh-meta__item"><GitBranch :size="12" :stroke-width="2" />main</span>
                  <span class="dh-meta__item"><GitCommitHorizontal :size="12" :stroke-width="2" />7d02b18</span>
                  <span class="dh-when">{{ r.when }}</span>
                </span>
              </span>
              <Badge tone="neutral" class="dh-badge dh-badge--old">
                <template #icon>
                  <span class="dh-mark" data-ready="true">
                    <Spinner :size="8" />
                    <i class="dh-dot" />
                  </span>
                </template>
                Ready
              </Badge>
              <span class="dh-time">{{ r.t }}</span>
            </div>
            <div v-else class="dh-row dh-row--filler">
              <span class="dh-lines">
                <Bar :w="[180, 150, 200][i - 1]" :h="8" :r="4" :tone="2" />
                <Bar :w="110" :h="7" :r="3.5" :tone="1" />
              </span>
              <Bar :w="52" :h="18" :r="9" :tone="1" />
              <Bar :w="28" :h="7" :r="3.5" :tone="1" />
            </div>
          </template>
        </div>
      </div>
    </Window>
  </Stage>
</template>
