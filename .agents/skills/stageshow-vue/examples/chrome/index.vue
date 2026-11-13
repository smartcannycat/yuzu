<script setup lang="ts">
import { h, onBeforeUnmount, onMounted, reactive } from 'vue'
import { Icon, Prompt, Stage, Window, type WindowProps } from '../../kit'
import './chrome.css'

// One native-size figure per option. The page reflows; the chrome does not
// shrink as part of a large sheet. All frame measurements come from Window.
const files = [
  { name: 'Brief.pdf', size: '24 KB' },
  { name: 'Notes.md', size: '4 KB' },
  { name: 'Sketch.fig', size: '86 KB' },
  { name: 'Assets.zip', size: '2 MB' },
]

const Tool = () =>
  h('span', { class: 'wc-tools' }, [
    h(Icon, { name: 'search', size: 14 }),
    h(Icon, { name: 'plus', size: 14 }),
  ])

const TallTool = () =>
  h('span', { class: 'wc-tall-tool' }, [
    h('span', { class: 'wc-tall-tool__icon' }, [
      h(
        'svg',
        {
          width: '16',
          height: '16',
          viewBox: '0 0 20 20',
          fill: 'none',
          stroke: 'currentColor',
          'stroke-width': '1.4',
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round',
          'aria-hidden': 'true',
        },
        [h('path', { d: 'M2.5 6V4.5h5L9 6h8.5v10h-15ZM10 9v4M8 11h4' })],
      ),
    ]),
    h('span', 'New folder'),
  ])

const Side = () =>
  h('div', { class: 'wc-side' }, [
    h('span', { 'data-active': '' }, 'All files'),
    h('span', 'Shared'),
    h('span', 'Archive'),
  ])

const HairlineUrl = () => h('span', { class: 'wc-address' }, 'files.example')

type Specimen = { id: string; title: string; note: string; props: WindowProps; cool?: boolean }
const specimens: Specimen[] = [
  { id: 'glass', title: 'Glass', note: 'Frosted frame and inset page.', props: { chrome: 'glass', url: 'files.example' } },
  { id: 'card', title: 'Card', note: 'Pale address field and a soft lifted edge.', props: { chrome: 'card', url: 'files.example' } },
  { id: 'hairline', title: 'Hairline', note: 'A short bar with a fine separator.', props: { chrome: 'hairline', url: HairlineUrl } },
  { id: 'terminal', title: 'Terminal', note: 'One dark surface, without a bar divider.', props: { chrome: 'terminal', title: 'workspace — zsh', lights: 'grey' } },
  { id: 'browser', title: 'Browser', note: 'Native address bar.', props: { url: 'files.example' } },
  { id: 'tabs', title: 'Browser with tabs', note: 'Tabs and back/forward controls.', props: { url: 'files.example', nav: true, tabs: ['Files', 'Docs'] } },
  { id: 'app', title: 'App toolbar', note: 'Title and controls in one bar.', props: { title: 'Files', toolbar: Tool } },
  { id: 'sidebar', title: 'Sidebar', note: 'Lights in a full-height sidebar.', props: { title: 'Files', toolbar: Tool, sidebarWidth: 96, sidebar: Side } },
  { id: 'large-lights', title: 'Larger lights', note: 'The native 12px traffic lights.', cool: true, props: { title: 'Files', toolbar: Tool, lightsSize: 'large' } },
  { id: 'floating-sidebar', title: 'Floating sidebar', note: 'An inset panel with nested corners.', cool: true, props: { title: 'Files', toolbar: Tool, sidebarWidth: 96, sidebarStyle: 'floating', sidebar: Side } },
  { id: 'tall-toolbar', title: 'Tall toolbar', note: 'A taller bar with inline controls and larger lights.', cool: true, props: { title: 'Files', toolbar: TallTool, lightsSize: 'large', barSize: 'tall' } },
  { id: 'combined', title: 'Combined', note: 'Floating sidebar, tall bar and larger lights.', cool: true, props: { title: 'Files', toolbar: TallTool, sidebarWidth: 96, sidebarStyle: 'floating', sidebar: Side, lightsSize: 'large', barSize: 'tall' } },
]

const widths = reactive<Record<string, number>>(
  Object.fromEntries(specimens.map(item => [item.id, 288])),
)
const pictureRefs = new Map<string, HTMLDivElement>()

function setPictureRef(id: string, el: any) {
  if (el instanceof HTMLDivElement) pictureRefs.set(id, el)
  else pictureRefs.delete(id)
}

const observers: ResizeObserver[] = []
onMounted(() => {
  for (const item of specimens) {
    const node = pictureRefs.get(item.id)
    if (!node) continue
    const measure = () => {
      if (node.clientWidth) widths[item.id] = node.clientWidth
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    observers.push(observer)
  }
})
onBeforeUnmount(() => {
  observers.forEach(o => o.disconnect())
})
</script>

<template>
  <div class="wc-gallery">
    <figure v-for="item in specimens" :key="item.id" class="wc-figure" :data-specimen="item.id">
      <div :ref="(el) => setPictureRef(item.id, el)" class="wc-picture">
        <Stage specimen :width="widths[item.id]" :height="224" :greys="item.cool ? 'cool' : undefined">
          <div class="wc-ground" :data-material="item.id">
            <Window v-bind="item.props" class="wc-window" :style="{ width: `${widths[item.id] - 32}px`, height: '176px' }">
              <div v-if="item.id === 'terminal'" class="wc-terminal">
                <Prompt>pwd</Prompt>
                <span>/workspace</span>
              </div>
              <div v-else class="wc-content" aria-label="Files">
                <div
                  v-for="(file, i) in files.slice(0, item.props.tabs ? 3 : 4)"
                  :key="file.name"
                  class="wc-file-row"
                  :data-selected="i === 0 || undefined"
                >
                  <Icon name="file" :size="14" />
                  <span>{{ file.name }}</span>
                  <span class="wc-file-size">{{ file.size }}</span>
                </div>
              </div>
            </Window>
          </div>
        </Stage>
      </div>
      <figcaption>
        <strong>{{ item.title }}</strong>
        <span>{{ item.note }}</span>
      </figcaption>
    </figure>
  </div>
</template>
