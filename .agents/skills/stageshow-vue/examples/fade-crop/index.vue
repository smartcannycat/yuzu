<script setup lang="ts">
import { Badge, Bar, Row, Stage, Text, Window } from '../../kit'
import './fade.css'

// A fade crop: a deployments page that sinks into the page instead of running
// off an edge. A still.
//
// What makes the fade read as deliberate:
// - Only the foot fades. The top and both sides are whole and hard-edged, so
//   the window is plainly a window, placed, not a smear.
// - It's a mask, not a color laid over the foot, so the window fades to
//   transparent and dissolves into whatever it sits on.
// - Only filler is under the fade: the real rows sit in the top half, the
//   placeholder rows carry on into the fade so the list reads as going on.
// - The mask is on a wrapper with room around the window, so the window
//   keeps its shadow on the top and sides; a mask on the window itself would
//   clip the shadow off.
//
// Real strings: the project, the newest deployment (status, branch, commit,
// age), and the one before it.

const ROWS = [
  { status: 'Ready', branch: 'main', commit: 'Fix checkout redirect loop', age: '2m ago', tone: 'success' as const },
  { status: 'Ready', branch: 'pricing-copy', commit: 'New annual plan wording', age: '1h ago', tone: 'success' as const },
]

const FILL = [
  [132, 168],
  [96, 140],
  [148, 120],
  [110, 176],
]
</script>

<template>
  <Stage :width="640" :height="360" :compact="{ below: 600, width: 358, height: 360 }" class="fc">
    <div class="fc-mask">
      <Window url="deploy.northwind.co" class="fc-win">
        <div class="fc-body">
          <div class="fc-head">
            <Text class="fc-title">Deployments</Text>
            <Bar :w="84" :h="22" :r="6" :tone="1" />
          </div>
          <div class="fc-list">
            <Row v-for="r in ROWS" :key="r.commit" :pad="0" class="fc-row">
              <template #lead>
                <Badge :tone="r.tone" dot>{{ r.status }}</Badge>
              </template>
              <template #title>
                <Text class="fc-commit">{{ r.commit }}</Text>
              </template>
              <template #subtitle>
                <Text class="fc-branch">{{ r.branch }}</Text>
              </template>
              <template #meta>
                <Text class="fc-age">{{ r.age }}</Text>
              </template>
            </Row>
            <Row v-for="([a, b], i) in FILL" :key="i" :pad="0" class="fc-row">
              <template #lead>
                <Bar :w="52" :h="20" :r="10" :tone="1" />
              </template>
              <template #title>
                <Bar :w="a" :h="8" :r="4" :tone="3" />
              </template>
              <template #subtitle>
                <Bar :w="b * 0.5" :h="7" :r="3.5" :tone="2" />
              </template>
              <template #meta>
                <Bar :w="40" :h="7" :r="3.5" :tone="2" />
              </template>
            </Row>
          </div>
        </div>
      </Window>
    </div>
  </Stage>
</template>
