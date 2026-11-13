<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import { useLook } from '../looks'
import './Avatar.css'

export interface AvatarProps {
  name?: string
  plain?: boolean
  size?: number
  tone?: 'accent' | 'ink' | 'success' | 'person' | 'ios'
  src?: string
  ring?: 'pending' | 'waiting' | 'confirmed' | 'declined'
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<AvatarProps>(), {
  name: '',
  plain: false,
  size: 24,
})

const PEOPLE = ['#c98f6e', '#6f9b7d', '#7b86c7', '#c47a9e', '#8c9ab0', '#c2a35a']
function hue(name: string) {
  let h = 0
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 9973
  return PEOPLE[h % PEOPLE.length]
}

const look = useLook()
const effectiveTone = computed(() => props.tone ?? (props.name ? 'person' : 'ink'))
const disc = computed(() => props.plain || look.fidelity === 'minimal')

const personStyle = computed(() => {
  if (effectiveTone.value === 'person' && !disc.value) {
    return { background: hue(props.name), color: '#fff' }
  }
  return undefined
})

const initials = computed(() => {
  const words = props.name.trim().split(/\s+/).filter(Boolean)
  if (effectiveTone.value === 'ios') {
    return (words[0]?.[0] ?? '') + (words.length > 1 ? words[words.length - 1]![0] : '')
  }
  return props.name.trim()[0] ?? ''
})

const avatarStyle = computed<CSSProperties>(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.round(props.size * (effectiveTone.value === 'ios' ? 0.4 : props.size < 24 ? 0.5 : 0.42))}px`,
  ...personStyle.value,
  ...props.style,
}))
</script>

<template>
  <span
    :class="['ss-avatar', props.className, props.class]"
    :data-tone="effectiveTone"
    :data-ring="props.ring"
    :style="avatarStyle"
    v-bind="$attrs"
  >
    <img v-if="props.src && !disc" :src="props.src" alt="" />
    <span v-else-if="!disc" class="ss-avatar__initial">{{ initials.toUpperCase() }}</span>
  </span>
</template>
