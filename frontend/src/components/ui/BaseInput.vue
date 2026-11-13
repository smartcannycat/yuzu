<script setup lang="ts">
import { X } from '@lucide/vue'
import { computed, useId, useSlots } from 'vue'

interface Props {
  id?: string
  label?: string
  helperText?: string
  error?: string
  placeholder?: string
  type?: 'text' | 'email' | 'password' | 'number' | 'search' | 'tel'
  disabled?: boolean
  readonly?: boolean
  required?: boolean
  clearable?: boolean
  clearLabel?: string
  autocomplete?: string
  inputmode?: 'text' | 'decimal' | 'numeric' | 'tel' | 'search' | 'email'
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  disabled: false,
  readonly: false,
  required: false,
  clearable: false,
  clearLabel: 'Очистить поле',
})

const modelValue = defineModel<string>({ default: '' })
const slots = useSlots()

const fallbackId = useId()
const inputId = computed(() => props.id ?? `yuzu-input-${fallbackId}`)
const helperId = computed(() => `${inputId.value}-helper`)
const errorId = computed(() => `${inputId.value}-error`)

const hasError = computed(() => Boolean(props.error))
const hasPrefix = computed(() => Boolean(slots.prefix))
const showClear = computed(
  () => props.clearable && !props.disabled && !props.readonly && modelValue.value.length > 0,
)
const hasSuffix = computed(() => Boolean(slots.suffix) || showClear.value)

const describedBy = computed(() => {
  const ids: string[] = []
  if (props.error) ids.push(errorId.value)
  else if (props.helperText) ids.push(helperId.value)
  return ids.length > 0 ? ids.join(' ') : undefined
})

function handleClear() {
  modelValue.value = ''
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label
      v-if="label"
      :for="inputId"
      class="text-text-secondary text-[13px] leading-tight font-medium"
    >
      <span>{{ label }}</span>
      <span v-if="required" class="text-danger ml-0.5" aria-hidden="true">*</span>
    </label>

    <div class="relative flex items-center">
      <span
        v-if="hasPrefix"
        class="text-text-muted pointer-events-none absolute left-3.5 flex items-center"
        aria-hidden="true"
      >
        <slot name="prefix" />
      </span>

      <input
        :id="inputId"
        v-model="modelValue"
        :type="type"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :required="required"
        :autocomplete="autocomplete"
        :inputmode="inputmode"
        :aria-invalid="hasError || undefined"
        :aria-describedby="describedBy"
        class="text-text-primary placeholder:text-text-muted disabled:bg-canvas disabled:text-text-muted h-11 w-full rounded-sm border text-[16px] leading-6 transition-[border-color,box-shadow,background-color] duration-[var(--duration-quick)] ease-[var(--ease-smooth-out)] focus:outline-none disabled:cursor-not-allowed"
        :class="[
          hasPrefix ? 'pl-10' : 'pl-3.5',
          hasSuffix ? 'pr-11' : 'pr-3.5',
          hasError
            ? 'border-danger focus:border-danger focus:ring-danger/15 bg-[#FFFBFB] focus:ring-3'
            : 'border-border bg-surface focus:border-border-focus focus:ring-accent/15 focus:ring-3',
        ]"
      />

      <div v-if="hasSuffix" class="absolute right-0.5 flex items-center gap-0.5">
        <button
          v-if="showClear"
          type="button"
          :aria-label="clearLabel"
          class="group/clear focus-visible:outline-accent flex h-11 w-11 cursor-pointer items-center justify-center rounded-sm focus-visible:outline-2 focus-visible:outline-offset-[-4px]"
          @click="handleClear"
        >
          <span
            class="text-text-muted group-hover/clear:bg-surface-inset group-hover/clear:text-text-primary flex h-7 w-7 items-center justify-center rounded-full transition-colors duration-[var(--duration-quick)]"
          >
            <X :size="15" :stroke-width="2" aria-hidden="true" />
          </span>
        </button>
        <slot name="suffix" />
      </div>
    </div>

    <p
      v-if="error"
      :id="errorId"
      role="alert"
      class="text-danger text-[12px] leading-snug font-medium"
    >
      {{ error }}
    </p>
    <p v-else-if="helperText" :id="helperId" class="text-text-secondary text-[12px] leading-snug">
      {{ helperText }}
    </p>
  </div>
</template>
