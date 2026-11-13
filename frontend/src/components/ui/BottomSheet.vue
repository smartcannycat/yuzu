<script setup lang="ts">
import { X } from '@lucide/vue'
import { onKeyStroke, useMediaQuery, useScrollLock } from '@vueuse/core'
import { computed, ref, useId, useTemplateRef, watch } from 'vue'

import { useFocusTrap } from '@/composables/useFocusTrap'

export type SheetPlacement = 'center' | 'left' | 'right'

interface Props {
  title?: string
  subtitle?: string
  closeLabel?: string
  closeOnBackdrop?: boolean
  maxWidth?: 'sm' | 'md' | 'lg'
  placement?: SheetPlacement
}

const MAX_WIDTH_CLASSES: Record<NonNullable<Props['maxWidth']>, string> = {
  sm: 'md:max-w-sm',
  md: 'md:max-w-lg',
  lg: 'md:max-w-2xl',
}

const BACKDROP_PLACEMENT_CLASSES: Record<SheetPlacement, string> = {
  center: 'md:items-center md:justify-center md:p-6',
  left: 'md:items-stretch md:justify-start md:p-4',
  right: 'md:items-stretch md:justify-end md:p-4',
}

const PANEL_PLACEMENT_CLASSES: Record<SheetPlacement, string> = {
  center: 'md:max-h-[90dvh]',
  left: 'md:h-full md:max-h-full',
  right: 'md:h-full md:max-h-full',
}

const props = withDefaults(defineProps<Props>(), {
  closeLabel: 'Закрыть окно',
  closeOnBackdrop: true,
  maxWidth: 'md',
  placement: 'center',
})

const open = defineModel<boolean>('open', { default: false })

const panelRef = useTemplateRef<HTMLDivElement>('panelRef')
const isDesktop = useMediaQuery('(min-width: 768px)')

const uid = useId()
const titleId = `yuzu-sheet-title-${uid}`
const descId = `yuzu-sheet-desc-${uid}`

const bodyTarget = typeof document !== 'undefined' ? document.body : null
const isScrollLocked = useScrollLock(bodyTarget)

watch(
  open,
  (isOpen) => {
    isScrollLocked.value = isOpen
  },
  { immediate: true },
)

useFocusTrap(panelRef, open)

onKeyStroke('Escape', (event) => {
  if (!open.value) return
  event.preventDefault()
  close()
})

const dragOffsetY = ref(0)
const isDragging = ref(false)
let touchStartY = 0

function onTouchStart(event: TouchEvent) {
  if (isDesktop.value) return
  const touch = event.touches[0]
  if (!touch) return
  touchStartY = touch.clientY
  isDragging.value = true
}

function onTouchMove(event: TouchEvent) {
  if (!isDragging.value || isDesktop.value) return
  const touch = event.touches[0]
  if (!touch) return
  const delta = touch.clientY - touchStartY
  dragOffsetY.value = delta > 0 ? delta : 0
}

function onTouchEnd() {
  if (!isDragging.value) return
  isDragging.value = false
  if (dragOffsetY.value > 72) {
    close()
  }
  dragOffsetY.value = 0
}

const maxWidthClass = computed(() => MAX_WIDTH_CLASSES[props.maxWidth])
const backdropPlacementClass = computed(() => BACKDROP_PLACEMENT_CLASSES[props.placement])
const panelPlacementClass = computed(() => PANEL_PLACEMENT_CLASSES[props.placement])

const dragStyle = computed(() => {
  if (isDesktop.value || dragOffsetY.value === 0) return undefined
  return {
    transform: `translateY(${dragOffsetY.value}px)`,
    transition: isDragging.value ? 'none' : undefined,
  }
})

function close() {
  open.value = false
}

function onBackdropClick() {
  if (props.closeOnBackdrop) {
    close()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="yuzu-backdrop">
      <div
        v-if="open"
        class="bg-text-primary/40 fixed inset-0 z-50 flex items-end justify-center backdrop-blur-[2px]"
        :class="backdropPlacementClass"
        @click.self="onBackdropClick"
      >
        <Transition :name="`yuzu-sheet-${placement}`" appear>
          <div
            v-if="open"
            ref="panelRef"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="title ? titleId : undefined"
            :aria-describedby="subtitle ? descId : undefined"
            tabindex="-1"
            :style="dragStyle"
            class="border-border bg-surface shadow-sheet md:shadow-modal flex max-h-[90dvh] w-full flex-col overflow-hidden rounded-t-xl border focus:outline-none md:rounded-xl"
            :class="[maxWidthClass, panelPlacementClass]"
          >
            <!-- Mobile grabber handle -->
            <div
              class="flex shrink-0 touch-none flex-col items-center pt-2.5 pb-1 md:hidden"
              @touchstart.passive="onTouchStart"
              @touchmove.passive="onTouchMove"
              @touchend="onTouchEnd"
            >
              <span class="bg-border-strong h-1 w-9 rounded-full" aria-hidden="true" />
            </div>

            <!-- Header -->
            <div
              class="border-border flex shrink-0 items-center justify-between gap-3 border-b px-5 py-3 md:pt-4"
            >
              <div class="flex min-w-0 flex-col gap-0.5">
                <h2
                  v-if="title"
                  :id="titleId"
                  class="text-text-primary text-[17px] leading-snug font-semibold"
                >
                  {{ title }}
                </h2>
                <p
                  v-if="subtitle"
                  :id="descId"
                  class="text-text-secondary text-[13px] leading-snug"
                >
                  {{ subtitle }}
                </p>
              </div>

              <button
                type="button"
                :aria-label="closeLabel"
                class="group/close focus-visible:outline-accent -mr-1.5 flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-[-4px]"
                @click="close"
              >
                <span
                  class="bg-surface-inset text-text-secondary group-hover/close:bg-border group-hover/close:text-text-primary flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-[var(--duration-quick)]"
                >
                  <X :size="16" :stroke-width="2" aria-hidden="true" />
                </span>
              </button>
            </div>

            <!-- Scrollable body -->
            <div class="flex-1 overflow-y-auto px-5 py-4">
              <slot />
            </div>

            <!-- Optional footer -->
            <div
              v-if="$slots.footer"
              class="border-border bg-surface shrink-0 border-t px-5 pt-3 pb-[max(16px,env(safe-area-inset-bottom))]"
            >
              <slot name="footer" />
            </div>
            <div v-else class="h-[env(safe-area-inset-bottom)] shrink-0 md:hidden" />
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.yuzu-backdrop-enter-active {
  transition: opacity var(--modal-open-dur) var(--ease-out);
}
.yuzu-backdrop-leave-active {
  transition: opacity var(--modal-close-dur) var(--ease-out);
}
.yuzu-backdrop-enter-from,
.yuzu-backdrop-leave-to {
  opacity: 0;
}

.yuzu-sheet-center-enter-active,
.yuzu-sheet-left-enter-active,
.yuzu-sheet-right-enter-active {
  transition:
    transform var(--modal-open-dur) var(--modal-ease),
    opacity var(--modal-open-dur) var(--modal-ease);
}
.yuzu-sheet-center-leave-active,
.yuzu-sheet-left-leave-active,
.yuzu-sheet-right-leave-active {
  transition:
    transform var(--modal-close-dur) var(--modal-ease),
    opacity var(--modal-close-dur) var(--modal-ease);
}
.yuzu-sheet-center-enter-from,
.yuzu-sheet-center-leave-to,
.yuzu-sheet-left-enter-from,
.yuzu-sheet-left-leave-to,
.yuzu-sheet-right-enter-from,
.yuzu-sheet-right-leave-to {
  opacity: 0;
  transform: translateY(100%);
}

@media (min-width: 768px) {
  .yuzu-sheet-center-enter-from,
  .yuzu-sheet-center-leave-to {
    opacity: 0;
    transform: translateY(8px) scale(0.96);
  }

  .yuzu-sheet-left-enter-from,
  .yuzu-sheet-left-leave-to {
    opacity: 0;
    transform: translateX(-28px);
  }

  .yuzu-sheet-right-enter-from,
  .yuzu-sheet-right-leave-to {
    opacity: 0;
    transform: translateX(28px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .yuzu-backdrop-enter-active,
  .yuzu-backdrop-leave-active,
  .yuzu-sheet-center-enter-active,
  .yuzu-sheet-center-leave-active,
  .yuzu-sheet-left-enter-active,
  .yuzu-sheet-left-leave-active,
  .yuzu-sheet-right-enter-active,
  .yuzu-sheet-right-leave-active {
    transition: none !important;
  }
}
</style>
