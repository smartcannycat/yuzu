<script setup lang="ts">
import { ref, onMounted, onUpdated, type CSSProperties, type VNode, h } from 'vue'
import './code.css'

export interface CodeLine {
  text: string
  kind?: 'add' | 'del'
  number?: boolean
}

const props = withDefaults(
  defineProps<{
    lines: (CodeLine | string)[]
    start?: number
    numbers?: boolean
    count?: number
    highlight?: boolean
    className?: string
    class?: any
    style?: CSSProperties | any
  }>(),
  {
    start: 1,
    numbers: true,
    highlight: true,
  },
)

const KEYWORDS =
  /^(const|let|var|function|return|if|else|await|async|import|from|export|default|new|true|false|null|undefined|for|of|in|while|try|catch|throw|class|extends|type|interface|def|self|None|True|False)$/

function tokenize(line: string): (string | VNode)[] {
  const out: (string | VNode)[] = []
  const re =
    /(\/\/.*$|#.*$)|('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|`(?:[^`\\]|\\.)*`)|(\b\d[\d._]*\b)|([A-Za-z_$][\w$]*)(?=\s*\()|([A-Za-z_$][\w$]*)/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(line))) {
    if (m.index > last) out.push(line.slice(last, m.index))
    const [text, com, str, num, call, word] = m
    const kind = com
      ? 'com'
      : str
        ? 'str'
        : num
          ? 'num'
          : call
            ? KEYWORDS.test(call)
              ? 'key'
              : 'fn'
            : word && KEYWORDS.test(word)
              ? 'key'
              : null
    out.push(kind ? h('span', { key: k++, class: `ss-code__${kind}` }, text) : text)
    last = m.index + text.length
  }
  if (last < line.length) out.push(line.slice(last))
  return out
}

const root = ref<HTMLDivElement | null>(null)

function markOver() {
  root.value?.querySelectorAll<HTMLElement>('.ss-code__text').forEach((t) => {
    t.toggleAttribute('data-over', t.scrollWidth > t.clientWidth + 1)
  })
}

onMounted(() => {
  markOver()
  const ro = new ResizeObserver(markOver)
  if (root.value) ro.observe(root.value)
})

onUpdated(() => {
  markOver()
})

function getLineInfo(raw: CodeLine | string, index: number, prevNumber: number) {
  const line = typeof raw === 'string' ? { text: raw } : raw
  const num = line.kind === 'del' || line.number === false ? prevNumber : prevNumber
  return { line, num }
}

const processedLines = () => {
  let n = props.start
  return props.lines.map((raw) => {
    const line = typeof raw === 'string' ? { text: raw } : raw
    const num = line.kind === 'del' || line.number === false ? n : n++
    return { line, num }
  })
}
</script>

<template>
  <div ref="root" :class="['ss-code', props.className, props.class]" :style="props.style">
    <div
      v-for="({ line, num }, i) in processedLines()"
      :key="i"
      class="ss-code__line"
      :data-kind="line.kind"
      :data-shown="props.count === undefined || i < props.count || undefined"
    >
      <span v-if="props.numbers" class="ss-code__num">
        {{ line.number === false ? '' : num }}
      </span>
      <span v-if="line.kind" class="ss-code__sigil">
        {{ line.kind === 'add' ? '+' : '−' }}
      </span>
      <span class="ss-code__text">
        <template v-if="props.highlight">
          <component
            v-for="(tok, idx) in tokenize(line.text)"
            :is="typeof tok === 'string' ? 'span' : tok"
            :key="idx"
          >
            {{ typeof tok === 'string' ? tok : undefined }}
          </component>
        </template>
        <template v-else>{{ line.text }}</template>
      </span>
    </div>
  </div>
</template>
