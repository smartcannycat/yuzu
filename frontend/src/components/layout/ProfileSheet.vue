<script setup lang="ts">
import { LogOut, ShieldCheck, User } from '@lucide/vue'

import { isMockMode } from '@/api'
import { BaseButton, BottomSheet, InsetListGroup, InsetListItem } from '@/components/ui'

interface Props {
  name: string | null | undefined
  email: string | undefined
}

defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  logout: []
}>()
</script>

<template>
  <BottomSheet v-model:open="open" title="Профиль" :subtitle="email" max-width="sm">
    <div class="flex flex-col gap-4">
      <InsetListGroup>
        <InsetListItem title="Имя" :value="name || 'Не указано'" squircle-color="#1D4ED8">
          <template #icon>
            <User :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>
        <InsetListItem
          title="Режим API"
          :value="isMockMode ? 'Mock' : 'Live'"
          squircle-color="#15803D"
        >
          <template #icon>
            <ShieldCheck :size="16" :stroke-width="2" />
          </template>
        </InsetListItem>
      </InsetListGroup>
    </div>

    <template #footer>
      <BaseButton variant="destructive" size="lg" block @click="emit('logout')">
        <template #icon-left>
          <LogOut :size="18" :stroke-width="2" />
        </template>
        Выйти из аккаунта
      </BaseButton>
    </template>
  </BottomSheet>
</template>
