<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import { useLook } from '../looks'
import { brandMarks, type BrandName, type BrandAsset } from '../brands'
import './BrandMark.css'

export type BrandMarkProps = {
  brand?: BrandName
  name?: string
  src?: string
  size?: number
  width?: number
  tile?: boolean
  surface?: 'light' | 'dark'
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<BrandMarkProps>(), {
  size: 28,
  tile: true,
})

const look = useLook()
const asset = computed<BrandAsset | undefined>(() =>
  props.brand ? brandMarks[props.brand] : undefined,
)

const dark = computed(() => {
  if (props.surface) return props.surface === 'dark'
  const t = look.theme
  return t === 'dark' || t === 'blueprint'
})

const label = computed(() => props.name ?? asset.value?.name ?? '')
const image = computed(() => {
  if (props.src) return props.src
  if (props.tile && asset.value?.tileArtwork) return asset.value.tileArtwork
  return dark.value ? asset.value?.dark : asset.value?.light
})

const assetSizing = computed(() => Boolean(asset.value && !props.src))
const frameWidth = computed(() =>
  props.width ?? (assetSizing.value && asset.value ? Math.round(props.size * asset.value.proportion) : props.size),
)

const lightTile = computed(
  () =>
    props.tile &&
    dark.value &&
    assetSizing.value &&
    asset.value &&
    asset.value.dark === asset.value.light,
)

const brandStyle = computed<CSSProperties>(() => ({
  width: `${frameWidth.value}px`,
  height: `${props.size}px`,
  borderRadius: `${Math.round(props.size * 0.24)}px`,
  background: props.tile && assetSizing.value ? asset.value?.tileBackground : undefined,
  ...props.style,
}))

const imgStyle = computed(() => {
  if (assetSizing.value && props.tile && asset.value) {
    return {
      width: `${asset.value.scale * 100}%`,
      height: `${asset.value.scale * 100}%`,
    }
  }
  return undefined
})

const initialFontSize = computed(() =>
  Math.round(props.size * (props.size < 24 ? 0.5 : 0.42)),
)
</script>

<template>
  <span
    :class="['ss-brand', props.className, props.class]"
    :data-tile="props.tile || undefined"
    :data-light-tile="lightTile || undefined"
    :data-brand="props.brand"
    :style="brandStyle"
    role="img"
    :aria-label="label"
  >
    <img
      v-if="image && look.fidelity !== 'minimal'"
      :src="image"
      alt=""
      :draggable="false"
      :style="imgStyle"
    />
    <span
      v-else
      class="ss-brand__initial"
      :style="{ fontSize: `${initialFontSize}px` }"
    >
      {{ look.fidelity === 'minimal' ? '' : label.trim()[0]?.toUpperCase() }}
    </span>
  </span>
</template>
