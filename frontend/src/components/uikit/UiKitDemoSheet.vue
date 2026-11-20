<script setup lang="ts">
import { BaseButton, BaseCard, BottomSheet, CostLadder } from '@/components/ui'

interface Props {
  topic: 'auction' | 'farpost'
}

defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })
</script>

<template>
  <BottomSheet
    v-model:open="open"
    :title="topic === 'auction' ? 'Замечания инспектора аукциона' : 'Смета ремонта (Farpost)'"
    :subtitle="
      topic === 'auction'
        ? 'TAA Chubu #3142 • Перевод с японского'
        : 'Контрактные детали во Владивостоке в заводской цвет'
    "
  >
    <div
      v-if="topic === 'auction'"
      class="text-text-primary flex flex-col gap-3 text-[14px] leading-relaxed"
    >
      <BaseCard variant="inset" padding="sm">
        <p class="text-text-primary font-medium">Перевод заметок инспектора</p>
        <p class="text-text-secondary mt-1">
          Руль слегка потёрт, лёгкое загрязнение салона, царапины на передней левой двери, следы
          подкраса на заднем бампере.
        </p>
      </BaseCard>
      <p class="text-text-secondary text-[13px]">
        Шторка поддерживает закрытие по Escape, клику на фон, свайпу за верхнюю планку на мобильных
        устройствах и ловушку фокуса для клавиатуры.
      </p>
    </div>

    <div v-else class="flex flex-col gap-3">
      <CostLadder
        :steps="[
          { label: 'Дверь передняя левая (в цвет 070)', value: 'от 18 000 ₽', active: true },
          { label: 'Снятие и монтаж детали', value: '5 000 ₽' },
          { label: 'Покраска (не требуется)', value: '0 ₽' },
          { label: 'PDR + полировка мелких сколов', value: '8 000 ₽' },
        ]"
        total-label="Итого расчётный ремонт"
        total-value="31 000 ₽"
      />
    </div>

    <template #footer>
      <BaseButton variant="primary" size="lg" block @click="open = false">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
