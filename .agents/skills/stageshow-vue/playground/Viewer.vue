<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { examples, groups } from './catalog'
import './viewer.css'

const urlParams = new URLSearchParams(window.location.search)
const initial = urlParams.get('example')

const name = ref(examples.some(e => e.id === initial) ? initial! : examples[0].id)
const phone = ref(false)
const still = ref(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
const motionOverride = ref(false)
const playing = ref(true)
const speed = ref(1)
const revision = ref(0)
const elapsed = ref(0)
const height = ref(460)
const ready = ref(false)
const staticScene = ref(false)
const error = ref<string | null>(null)

const iframe = ref<HTMLIFrameElement | null>(null)
const visible = ref(false)
const lesson = ref(urlParams.get('lesson') ?? 'label')
const annotation = ref(urlParams.get('annotation') ?? 'collect')

const selected = computed(() => examples.find(e => e.id === name.value) || examples[0])
const transportDisabled = computed(() => !ready.value || still.value || staticScene.value)

const source = computed(() => {
  return `?embed=${name.value}&still=${still.value ? 1 : 0}${
    name.value === 'contrasts'
      ? `&lesson=${encodeURIComponent(lesson.value)}`
      : name.value === 'annotations'
      ? `&annotation=${encodeURIComponent(annotation.value)}`
      : ''
  }`
})

function send(data: object) {
  iframe.value?.contentWindow?.postMessage({ type: 'stageshow:control', ...data }, window.location.origin)
}

function handleMediaChange(e: MediaQueryListEvent) {
  if (!motionOverride.value) {
    still.value = e.matches
  }
}

function receive(event: MessageEvent) {
  if (event.origin !== window.location.origin || event.source !== iframe.value?.contentWindow || event.data?.type !== 'stageshow:status') return
  if (typeof event.data.lesson === 'string') {
    lesson.value = event.data.lesson
    const url = new URL(window.location.href)
    url.searchParams.set('lesson', event.data.lesson)
    window.history.replaceState(null, '', url)
  }
  if (Number.isFinite(event.data.elapsed)) {
    elapsed.value = event.data.elapsed
  }
  if (typeof event.data.annotation === 'string') {
    annotation.value = event.data.annotation
    const url = new URL(window.location.href)
    url.searchParams.set('annotation', event.data.annotation)
    window.history.replaceState(null, '', url)
  }
  if (typeof event.data.staticScene === 'boolean') {
    staticScene.value = event.data.staticScene
  }
  if (Number.isFinite(event.data.height)) {
    height.value = Math.max(1, event.data.height)
  }
  if (event.data.error) {
    error.value = String(event.data.error)
    ready.value = false
    playing.value = false
  } else if (event.data.ready) {
    ready.value = true
    send({ playing: playing.value && !still.value, speed: speed.value, visible: visible.value })
  }
}

let mediaQuery: MediaQueryList | null = null
let observer: IntersectionObserver | null = null

onMounted(() => {
  mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  mediaQuery.addEventListener('change', handleMediaChange)
  window.addEventListener('message', receive)

  observer = new IntersectionObserver(([entry]) => {
    visible.value = entry.isIntersecting
    send({ visible: visible.value })
  })
  if (iframe.value) {
    observer.observe(iframe.value)
  }
})

onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', handleMediaChange)
  window.removeEventListener('message', receive)
  if (observer) observer.disconnect()
})

watch([playing, speed, still], () => {
  send({ playing: playing.value && !still.value, speed: speed.value })
})

watch([name, revision, still], () => {
  ready.value = false
  staticScene.value = false
  elapsed.value = 0
  error.value = null
  const url = new URL(window.location.href)
  url.searchParams.set('example', name.value)
  window.history.replaceState(null, '', url)
})

function replay() {
  revision.value++
}

function handleIframeLoad() {
  send({ playing: playing.value && !still.value, speed: speed.value, visible: visible.value })
}
</script>

<template>
  <main class="pg" :data-reduced-motion="still || undefined">
    <header class="pg-header">
      <a class="pg-brand" href="./">Stageshow</a>
      <span class="pg-eyebrow">Playground</span>
    </header>

    <div class="pg-picker">
      <label for="example-choice">Example</label>
      <select id="example-choice" v-model="name">
        <optgroup v-for="group in groups" :key="group" :label="group">
          <option
            v-for="e in examples.filter(ex => ex.group === group)"
            :key="e.id"
            :value="e.id"
          >
            {{ e.name }}
          </option>
        </optgroup>
      </select>
    </div>

    <section class="pg-preview" aria-label="Example preview">
      <div class="pg-toolbar">
        <div class="pg-segment" aria-label="Preview width">
          <button :aria-pressed="!phone" @click="phone = false">Desktop</button>
          <button :aria-pressed="phone" @click="phone = true">Phone</button>
        </div>
        <label class="pg-still">
          <input
            type="checkbox"
            :checked="still"
            @change="(e: Event) => { motionOverride = true; still = (e.target as HTMLInputElement).checked }"
          />
          Reduced motion
        </label>
      </div>

      <div class="pg-canvas" :data-phone="phone || undefined" :data-grid="selected.kind === 'Grid' || undefined">
        <iframe
          :key="`${name}-${revision}-${still}`"
          ref="iframe"
          :title="selected.name"
          :src="source"
          :style="{ height: `${height}px` }"
          @load="handleIframeLoad"
        />
      </div>

      <p v-if="error" role="alert">Preview stopped: {{ error }}. Check the console, fix the example, then select Replay.</p>

      <div class="pg-transport">
        <div class="pg-buttons">
          <button
            class="pg-play"
            :data-playing="playing || undefined"
            :disabled="transportDisabled"
            :aria-label="playing ? 'Pause' : 'Play'"
            @click="playing = !playing"
          >
            <svg class="pg-play-icon" viewBox="0 0 16 16" aria-hidden="true">
              <path class="pg-play-icon-left" :d="playing ? 'M4 3L6.5 3L6.5 13L4 13Z' : 'M5 3L9 5.5L9 10.5L5 13Z'" />
              <path class="pg-play-icon-right" :d="playing ? 'M9.5 3L12 3L12 13L9.5 13Z' : 'M9 5.5L13 8L13 8L9 10.5Z'" />
            </svg>
            <span class="pg-play-label" aria-hidden="true">
              <span class="pg-play-word">Play</span>
              <span class="pg-pause-word">Pause</span>
            </span>
          </button>
          <button :disabled="transportDisabled" title="Advance one frame" @click="playing = false; send({ step: true })">
            Step
          </button>
          <button @click="replay">Replay</button>
        </div>

        <div class="pg-time">
          <output aria-label="Current time">
            {{ ((still || staticScene ? 0 : elapsed) / 1000).toFixed(2) }}<span>s</span>
          </output>
          <select
            v-model.number="speed"
            aria-label="Playback speed"
            :disabled="transportDisabled"
          >
            <option :value="0.25">¼×</option>
            <option :value="0.5">½×</option>
            <option :value="1">1×</option>
            <option :value="2">2×</option>
          </select>
        </div>
      </div>
    </section>

    <section class="pg-caption">
      <div>
        <h2>{{ selected.name }}</h2>
        <p>{{ selected.note }}</p>
      </div>
      <code>{{ name === 'contrasts' ? 'teaching/contrasts.vue' : `examples/${name}/` }}</code>
    </section>

    <footer class="pg-footer">
      <span>{{ still ? 'The reduced-motion poster is shown.' : staticScene ? 'This example is static.' : 'Pause playback to step through individual frames.' }}</span>
    </footer>
  </main>
</template>
