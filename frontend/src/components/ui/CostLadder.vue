<script setup lang="ts">
export interface CostLadderStep {
  label: string
  value: string
  hint?: string
  active?: boolean
}

interface Props {
  steps: CostLadderStep[]
  totalLabel?: string
  totalValue?: string
}

defineProps<Props>()
</script>

<template>
  <div class="flex flex-col">
    <ol class="relative flex flex-col">
      <li
        v-for="(step, index) in steps"
        :key="`${index}-${step.label}`"
        class="not-last:before:bg-border relative flex items-start justify-between gap-4 py-2.5 not-last:before:absolute not-last:before:top-7 not-last:before:-bottom-2.5 not-last:before:left-[10px] not-last:before:w-0.5 not-last:before:content-['']"
      >
        <div class="flex min-w-0 items-start gap-3.5">
          <span
            aria-hidden="true"
            class="relative z-10 mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 text-[11px] font-semibold tabular-nums transition-colors duration-150"
            :class="
              step.active
                ? 'border-accent bg-accent-subtle text-accent'
                : 'border-border bg-surface text-text-secondary'
            "
          >
            {{ index + 1 }}
          </span>
          <div class="flex min-w-0 flex-col">
            <span class="text-text-primary text-[14px] leading-snug font-normal">
              {{ step.label }}
            </span>
            <span v-if="step.hint" class="text-text-secondary text-[12px] leading-snug">
              {{ step.hint }}
            </span>
          </div>
        </div>

        <span
          class="text-text-primary shrink-0 text-[15px] leading-snug font-semibold tabular-nums"
        >
          {{ step.value }}
        </span>
      </li>
    </ol>

    <div
      v-if="totalLabel && totalValue"
      class="bg-surface-inset mt-3.5 flex flex-wrap items-baseline justify-between gap-2 rounded-sm p-4"
    >
      <span class="text-text-secondary text-[13px] font-semibold tracking-[0.04em] uppercase">
        {{ totalLabel }}
      </span>
      <span class="text-accent text-[24px] leading-tight font-semibold tabular-nums">
        {{ totalValue }}
      </span>
    </div>
  </div>
</template>
