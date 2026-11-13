<script setup lang="ts">
import { Pencil, RotateCcw } from '@lucide/vue'
import { computed, nextTick, ref, watch } from 'vue'

import {
  clampBidJpy,
  clampBidRub,
  parsePositiveIntegerInput,
} from '@/components/lots/detail/lotPresentation'
import { BaseButton, BaseCard } from '@/components/ui'
import { formatJpy, formatRub } from '@/utils/formatters'

interface Props {
  bidJpy: number
  displayBidRub: number
  jpyRate: number
  minJpy: number
  maxJpy: number
  stepJpy: number
  showReset?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showReset: false,
})

const emit = defineEmits<{
  sliderInput: [bidJpy: number]
  sliderCommit: []
  commitJpy: [bidJpy: number]
  commitRub: [bidRub: number]
  reset: []
}>()

const isEditingJpy = ref(false)
const jpyTextInput = ref('')
const jpyInputRef = ref<HTMLInputElement | null>(null)

const isEditingRub = ref(false)
const rubTextInput = ref('')
const rubInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.bidJpy,
  () => {
    isEditingJpy.value = false
    isEditingRub.value = false
  },
)

const effectiveMinJpy = computed(() => Math.min(props.minJpy, props.bidJpy))
const effectiveMaxJpy = computed(() => Math.max(props.maxJpy, props.bidJpy))

function handleSliderInput(event: Event): void {
  const target = event.target as HTMLInputElement
  const parsed = Number(target.value)
  if (!Number.isFinite(parsed) || parsed <= 0) return
  emit('sliderInput', clampBidJpy(parsed))
}

async function startEditingJpy(): Promise<void> {
  isEditingRub.value = false
  jpyTextInput.value = String(Math.round(props.bidJpy))
  isEditingJpy.value = true
  await nextTick()
  jpyInputRef.value?.focus()
  jpyInputRef.value?.select()
}

function cancelJpyEdit(): void {
  isEditingJpy.value = false
}

function submitJpyEdit(): void {
  if (!isEditingJpy.value) return
  isEditingJpy.value = false
  const parsed = parsePositiveIntegerInput(jpyTextInput.value)
  if (parsed === null) return
  const clamped = clampBidJpy(parsed)
  if (clamped !== props.bidJpy) {
    emit('commitJpy', clamped)
  }
}

async function startEditingRub(): Promise<void> {
  isEditingJpy.value = false
  rubTextInput.value = String(Math.round(props.displayBidRub))
  isEditingRub.value = true
  await nextTick()
  rubInputRef.value?.focus()
  rubInputRef.value?.select()
}

function cancelRubEdit(): void {
  isEditingRub.value = false
}

function submitRubEdit(): void {
  if (!isEditingRub.value) return
  isEditingRub.value = false
  const parsed = parsePositiveIntegerInput(rubTextInput.value)
  if (parsed === null) return
  const clampedRub = clampBidRub(parsed)
  if (clampedRub !== props.displayBidRub) {
    emit('commitRub', clampedRub)
  }
}
</script>

<template>
  <BaseCard variant="surface" padding="md">
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0 flex-1">
        <span class="text-text-secondary text-[12px] font-medium">
          Максимальная ставка на аукционе
        </span>

        <!-- Inline Editable JPY -->
        <div class="mt-1">
          <div
            v-if="isEditingJpy"
            class="border-accent bg-surface ring-accent/15 inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 ring-2"
          >
            <input
              ref="jpyInputRef"
              v-model="jpyTextInput"
              type="text"
              inputmode="numeric"
              aria-label="Введите ставку в иенах"
              class="text-text-primary w-32 bg-transparent text-[22px] leading-tight font-semibold tabular-nums outline-none"
              @keydown.enter.prevent="submitJpyEdit"
              @keydown.escape.prevent="cancelJpyEdit"
              @blur="submitJpyEdit"
            />
            <span class="text-text-secondary text-[18px] font-semibold">¥</span>
          </div>

          <button
            v-else
            type="button"
            aria-label="Изменить ставку в иенах"
            title="Нажмите, чтобы ввести точную ставку в иенах"
            class="group hover:bg-surface-inset focus-visible:outline-accent -mx-1.5 inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-0.5 transition-colors focus-visible:outline-2"
            @click="startEditingJpy"
          >
            <span
              class="text-text-primary border-border group-hover:border-accent border-b border-dashed text-[24px] leading-tight font-semibold tabular-nums transition-colors"
            >
              {{ formatJpy(bidJpy) }}
            </span>
            <Pencil
              :size="14"
              class="text-text-muted group-hover:text-accent shrink-0 transition-colors"
            />
          </button>
        </div>

        <!-- Inline Editable RUB -->
        <div class="mt-1">
          <div
            v-if="isEditingRub"
            class="border-accent bg-surface ring-accent/15 inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 ring-2"
          >
            <span class="text-text-secondary text-[13px]">≈</span>
            <input
              ref="rubInputRef"
              v-model="rubTextInput"
              type="text"
              inputmode="numeric"
              aria-label="Введите ставку в рублях"
              class="text-text-primary w-28 bg-transparent text-[14px] font-medium tabular-nums outline-none"
              @keydown.enter.prevent="submitRubEdit"
              @keydown.escape.prevent="cancelRubEdit"
              @blur="submitRubEdit"
            />
            <span class="text-text-secondary text-[13px] font-medium">₽</span>
          </div>

          <button
            v-else
            type="button"
            aria-label="Изменить ставку в рублях"
            title="Нажмите, чтобы ввести бюджет ставки в рублях"
            class="group hover:bg-surface-inset focus-visible:outline-accent -mx-1.5 inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-0.5 transition-colors focus-visible:outline-2"
            @click="startEditingRub"
          >
            <span
              class="text-text-secondary border-border group-hover:border-accent group-hover:text-text-primary border-b border-dashed text-[13px] tabular-nums transition-colors"
            >
              ≈ {{ formatRub(displayBidRub) }}
            </span>
            <Pencil
              :size="12"
              class="text-text-muted group-hover:text-accent shrink-0 transition-colors"
            />
          </button>
        </div>
      </div>

      <BaseButton v-if="showReset" variant="ghost" size="sm" pill @click="emit('reset')">
        <template #icon-left>
          <RotateCcw :size="14" />
        </template>
        Сбросить
      </BaseButton>
    </div>

    <div class="mt-3">
      <input
        type="range"
        aria-label="Максимальная ставка на аукционе в иенах"
        :min="effectiveMinJpy"
        :max="effectiveMaxJpy"
        :step="stepJpy"
        :value="bidJpy"
        class="accent-accent bg-surface-inset h-2 w-full cursor-pointer appearance-none rounded-full"
        @input="handleSliderInput"
        @change="emit('sliderCommit')"
      />

      <div class="text-text-muted mt-1 flex items-center justify-between text-[11px] tabular-nums">
        <span>{{ formatJpy(effectiveMinJpy) }}</span>
        <span>{{ formatJpy(effectiveMaxJpy) }}</span>
      </div>
    </div>
  </BaseCard>
</template>
