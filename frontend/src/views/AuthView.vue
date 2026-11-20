<script setup lang="ts">
import { CircleAlert, Eye, EyeOff, Lock, Mail, User } from '@lucide/vue'
import { computed, ref } from 'vue'

import { isMockMode } from '@/api'
import {
  BaseButton,
  BaseCard,
  BaseInput,
  BrandLogo,
  SegmentedControl,
  type SegmentOption,
} from '@/components/ui'
import { NAME_MAX_LENGTH, PASSWORD_MAX_LENGTH, type AuthMode } from '@/utils/validation'
import AuthMockDemoBanner from '@/views/helpers/AuthMockDemoBanner.vue'
import { useAuthForm } from '@/views/helpers/useAuthForm'

const modeOptions: SegmentOption<AuthMode>[] = [
  { value: 'login', label: 'Вход' },
  { value: 'register', label: 'Регистрация' },
]

const showPassword = ref(false)
const passwordInputType = computed(() => (showPassword.value ? 'text' : 'password'))

const {
  authStore,
  mode,
  form,
  fieldErrors,
  serverError,
  demoCredentials,
  isRegister,
  showSwitchToLoginHint,
  handleBlur,
  handleInputUpdate,
  applyDemoCredentials,
  switchToLoginFromConflict,
  handleSubmit,
} = useAuthForm()
</script>

<template>
  <main class="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col justify-center gap-5 px-4 py-8">
    <header class="flex flex-col items-start gap-2 px-1">
      <BrandLogo layout="auth" />
    </header>

    <BaseCard padding="lg" class="flex flex-col gap-5">
      <SegmentedControl
        v-model="mode"
        :options="modeOptions"
        ariaLabel="Переключение между входом и регистрацией"
        full-width
      />

      <div class="flex flex-col gap-1">
        <h1 class="text-text-primary text-[22px] leading-tight font-semibold tracking-[-0.015em]">
          {{ isRegister ? 'Создать аккаунт' : 'Вход в аккаунт' }}
        </h1>
        <p class="text-text-secondary text-[14px] leading-snug">
          {{
            isRegister
              ? 'Сохраняйте расчёты пошлин, смету ремонта и историю аукционных проверок.'
              : 'Войдите, чтобы открыть ваши расчёты и очередь обработки листов.'
          }}
        </p>
      </div>

      <div
        v-if="serverError"
        role="alert"
        class="bg-danger-bg text-danger flex flex-col gap-2 rounded-sm px-3.5 py-3 text-[13px] leading-snug"
      >
        <div class="flex items-start gap-2.5">
          <CircleAlert :size="16" :stroke-width="2" class="mt-0.5 shrink-0" aria-hidden="true" />
          <div class="flex min-w-0 flex-col gap-0.5">
            <span class="font-semibold">{{ serverError.title }}</span>
            <span>{{ serverError.detail }}</span>
          </div>
        </div>

        <button
          v-if="showSwitchToLoginHint"
          type="button"
          class="text-accent hover:text-accent-hover cursor-pointer self-start pl-6 text-[13px] font-medium underline underline-offset-2"
          @click="switchToLoginFromConflict"
        >
          Перейти ко входу с этим email
        </button>
      </div>

      <form class="flex flex-col gap-4" novalidate @submit.prevent="handleSubmit">
        <BaseInput
          v-if="isRegister"
          v-model="form.name"
          label="Имя (необязательно)"
          placeholder="Например, Алексей"
          autocomplete="name"
          :maxlength="NAME_MAX_LENGTH"
          :error="fieldErrors.name"
          :disabled="authStore.isSubmitting"
          @update:model-value="handleInputUpdate('name')"
          @blur="handleBlur('name')"
        >
          <template #prefix>
            <User :size="16" :stroke-width="1.75" />
          </template>
        </BaseInput>

        <BaseInput
          v-model="form.email"
          label="Email"
          type="email"
          inputmode="email"
          autocomplete="email"
          placeholder="alex@example.com"
          required
          clearable
          clear-label="Очистить email"
          :error="fieldErrors.email"
          :disabled="authStore.isSubmitting"
          @update:model-value="handleInputUpdate('email')"
          @blur="handleBlur('email')"
        >
          <template #prefix>
            <Mail :size="16" :stroke-width="1.75" />
          </template>
        </BaseInput>

        <BaseInput
          v-model="form.password"
          label="Пароль"
          :type="passwordInputType"
          :autocomplete="isRegister ? 'new-password' : 'current-password'"
          placeholder="Минимум 8 символов"
          required
          :maxlength="PASSWORD_MAX_LENGTH"
          :helper-text="isRegister ? 'От 8 до 128 символов' : undefined"
          :error="fieldErrors.password"
          :disabled="authStore.isSubmitting"
          @update:model-value="handleInputUpdate('password')"
          @blur="handleBlur('password')"
        >
          <template #prefix>
            <Lock :size="16" :stroke-width="1.75" />
          </template>
          <template #suffix>
            <button
              type="button"
              :aria-label="showPassword ? 'Скрыть пароль' : 'Показать пароль'"
              :aria-pressed="showPassword"
              class="text-text-muted hover:text-text-primary focus-visible:outline-accent flex h-11 w-11 cursor-pointer items-center justify-center rounded-sm transition-colors duration-[var(--duration-quick)] focus-visible:outline-2 focus-visible:outline-offset-[-4px]"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" :size="17" :stroke-width="1.75" aria-hidden="true" />
              <Eye v-else :size="17" :stroke-width="1.75" aria-hidden="true" />
            </button>
          </template>
        </BaseInput>

        <BaseButton
          type="submit"
          variant="primary"
          size="lg"
          block
          :loading="authStore.isSubmitting"
          class="mt-1"
        >
          {{ isRegister ? 'Создать аккаунт' : 'Войти' }}
        </BaseButton>
      </form>
    </BaseCard>

    <AuthMockDemoBanner
      v-if="isMockMode && demoCredentials"
      :email="demoCredentials.email"
      :disabled="authStore.isSubmitting"
      @apply="applyDemoCredentials"
    />
  </main>
</template>
