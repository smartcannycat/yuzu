<script setup lang="ts">
import { CheckCircle2, LogOut, ShieldCheck, User } from '@lucide/vue'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { isMockMode } from '@/api'
import {
  BaseBadge,
  BaseButton,
  BaseCard,
  BottomSheet,
  BrandLogo,
  InsetListGroup,
  InsetListItem,
} from '@/components/ui'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isProfileOpen = ref(false)

async function handleLogout(): Promise<void> {
  isProfileOpen.value = false
  authStore.logout()
  await router.replace({ name: 'auth' })
}
</script>

<template>
  <main class="mx-auto flex min-h-dvh w-full max-w-[680px] flex-col gap-5 px-4 py-6">
    <header class="flex items-center justify-between gap-3">
      <BrandLogo layout="header" />

      <button
        type="button"
        aria-label="Открыть меню профиля"
        class="border-border bg-surface hover:bg-surface-hover active:bg-surface-inset focus-visible:outline-accent flex h-10 max-w-[200px] cursor-pointer items-center gap-2 rounded-full border pr-3 pl-1.5 transition-colors duration-[var(--duration-quick)] focus-visible:outline-2 focus-visible:outline-offset-2"
        @click="isProfileOpen = true"
      >
        <span
          class="bg-accent-subtle text-accent flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold"
        >
          {{ authStore.initials }}
        </span>
        <span class="text-text-primary truncate text-[13px] font-medium">
          {{ authStore.displayName }}
        </span>
      </button>
    </header>

    <BaseCard padding="lg" class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <BaseBadge variant="success">
          <template #icon>
            <CheckCircle2 :size="14" :stroke-width="2" />
          </template>
          Сессия активна
        </BaseBadge>

        <BaseBadge variant="neutral">
          {{ isMockMode ? 'Mock API' : 'Backend API' }}
        </BaseBadge>
      </div>

      <div class="flex flex-col gap-1.5">
        <h1 class="text-text-primary text-[22px] leading-tight font-semibold tracking-[-0.015em]">
          Добро пожаловать, {{ authStore.displayName }}
        </h1>
        <p class="text-text-secondary text-[14px] leading-relaxed">
          Авторизация (Экран 0) и JWT-клиент с автообновлением токена настроены. Следующий шаг —
          реализация главного дашборда лотов (Экран 1).
        </p>
      </div>
    </BaseCard>

    <InsetListGroup title="Разделы">
      <InsetListItem
        title="Профиль и сессия"
        :subtitle="authStore.user?.email"
        value="Аккаунт"
        squircle-color="#FF6B00"
        interactive
        chevron
        @click="isProfileOpen = true"
      >
        <template #icon>
          <User :size="17" :stroke-width="2" />
        </template>
      </InsetListItem>
    </InsetListGroup>

    <BottomSheet
      v-model:open="isProfileOpen"
      title="Профиль"
      :subtitle="authStore.user?.email"
      max-width="sm"
    >
      <div class="flex flex-col gap-4">
        <InsetListGroup>
          <InsetListItem
            title="Имя"
            :value="authStore.user?.name || 'Не указано'"
            squircle-color="#1D4ED8"
          >
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
        <BaseButton variant="destructive" size="lg" block @click="handleLogout">
          <template #icon-left>
            <LogOut :size="18" :stroke-width="2" />
          </template>
          Выйти из аккаунта
        </BaseButton>
      </template>
    </BottomSheet>
  </main>
</template>
