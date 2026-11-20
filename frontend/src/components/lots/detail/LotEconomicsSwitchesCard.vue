<script setup lang="ts">
import { BaseButton, BaseCard, BaseSwitch } from '@/components/ui'
import { formatRub } from '@/utils/formatters'

interface Props {
  utilDescription: string
  isUtilModeForcedCommercial: boolean
  repairTotalRub: number
  powerHp: number | null
  isRecalculating: boolean
}

defineProps<Props>()

const commercialUtil = defineModel<boolean>('commercialUtil', { required: true })
const includeRepairs = defineModel<boolean>('includeRepairs', { required: true })
const powerHpInput = defineModel<string>('powerHpInput', { required: true })

const emit = defineEmits<{
  toggleSwitch: []
  applyPower: []
}>()
</script>

<template>
  <BaseCard variant="surface" padding="md">
    <div class="flex flex-col divide-y divide-[#E5E5EA]">
      <div class="pb-3">
        <BaseSwitch
          v-model="commercialUtil"
          label="Коммерческий утильсбор"
          :description="utilDescription"
          :disabled="isUtilModeForcedCommercial"
          @update:model-value="emit('toggleSwitch')"
        />
      </div>

      <div class="py-3">
        <BaseSwitch
          v-model="includeRepairs"
          label="Включать смету ремонта Farpost"
          :description="`Учтёт ${formatRub(repairTotalRub)} на кузовные детали и работы`"
          @update:model-value="emit('toggleSwitch')"
        />
      </div>

      <div class="pt-3">
        <label
          for="simulator-custom-power-hp"
          class="text-text-primary block text-[14px] font-medium"
        >
          Мощность двигателя (л.с.)
        </label>
        <p class="text-text-secondary mt-0.5 text-[12px]">
          {{
            powerHp === null
              ? 'Для подтверждения льготного утильсбора или акциза на EV укажите мощность вручную'
              : 'Уточните мощность при расхождении с каталогом Drom'
          }}
        </p>
        <form class="mt-2 flex items-center gap-2" @submit.prevent="emit('applyPower')">
          <input
            id="simulator-custom-power-hp"
            v-model="powerHpInput"
            type="text"
            inputmode="numeric"
            placeholder="Напр. 150"
            class="border-border bg-surface text-text-primary focus:border-accent w-28 rounded-sm border px-2.5 py-1.5 text-[14px] tabular-nums outline-none"
          />
          <BaseButton type="submit" variant="secondary" size="sm" :disabled="isRecalculating">
            Применить
          </BaseButton>
        </form>
      </div>
    </div>
  </BaseCard>
</template>
