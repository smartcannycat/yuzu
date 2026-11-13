<script setup lang="ts">
import { CircleAlert, Eye, EyeOff, Lock, Mail, Sparkles, User } from '@lucide/vue'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { DEMO_ACCOUNT_CREDENTIALS, isMockMode } from '@/api'
import {
  BaseBadge,
  BaseButton,
  BaseCard,
  BaseInput,
  BrandLogo,
  SegmentedControl,
  type SegmentOption,
} from '@/components/ui'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/api'
import {
  NAME_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  validateAuthForm,
  validateEmail,
  validateName,
  validatePassword,
  type AuthField,
  type AuthFieldErrors,
  type AuthMode,
} from '@/utils/validation'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

function resolveInitialMode(): AuthMode {
  if (route.name === 'register' || route.query.mode === 'register') {
    return 'register'
  }
  return 'login'
}

const mode = ref<AuthMode>(resolveInitialMode())

const modeOptions: SegmentOption<AuthMode>[] = [
  { value: 'login', label: 'Вход' },
  { value: 'register', label: 'Регистрация' },
]

const form = reactive({
  email: '',
  password: '',
  name: '',
})

const touched = reactive<Record<AuthField, boolean>>({
  email: false,
  password: false,
  name: false,
})

const fieldErrors = ref<AuthFieldErrors>({})
const serverError = ref<{ status: number; title: string; detail: string } | null>(null)
const showPassword = ref(false)

const isRegister = computed(() => mode.value === 'register')
const passwordInputType = computed(() => (showPassword.value ? 'text' : 'password'))
const showSwitchToLoginHint = computed(() => isRegister.value && serverError.value?.status === 409)

watch(
  () => [route.name, route.query.mode] as const,
  ([routeName, queryMode]) => {
    if (routeName === 'register' || queryMode === 'register') {
      mode.value = 'register'
    } else if (routeName === 'login' || queryMode === 'login') {
      mode.value = 'login'
    }
  },
)

watch(mode, () => {
  serverError.value = null
  fieldErrors.value = {}
  touched.email = false
  touched.password = false
  touched.name = false
})

function validateSingleField(field: AuthField): void {
  const nextErrors: AuthFieldErrors = { ...fieldErrors.value }
  let errorMessage: string | undefined

  if (field === 'email') {
    errorMessage = validateEmail(form.email)
  } else if (field === 'password') {
    errorMessage = validatePassword(form.password, mode.value)
  } else if (field === 'name' && isRegister.value) {
    errorMessage = validateName(form.name)
  }

  if (errorMessage) {
    nextErrors[field] = errorMessage
  } else {
    delete nextErrors[field]
  }
  fieldErrors.value = nextErrors
}

function handleBlur(field: AuthField): void {
  touched[field] = true
  validateSingleField(field)
}

function handleInputUpdate(field: AuthField): void {
  if (serverError.value) {
    serverError.value = null
  }
  if (touched[field] || fieldErrors.value[field]) {
    validateSingleField(field)
  }
}

function applyDemoCredentials(): void {
  mode.value = 'login'
  form.email = DEMO_ACCOUNT_CREDENTIALS.email
  form.password = DEMO_ACCOUNT_CREDENTIALS.password
  fieldErrors.value = {}
  serverError.value = null
}

function switchToLoginFromConflict(): void {
  mode.value = 'login'
  form.password = ''
}

function resolvePostAuthTarget() {
  const redirectParam = route.query.redirect
  if (
    typeof redirectParam === 'string' &&
    redirectParam.startsWith('/') &&
    !redirectParam.startsWith('//')
  ) {
    return redirectParam
  }
  return { name: 'home' as const }
}

async function handleSubmit(): Promise<void> {
  if (authStore.isSubmitting) return
  serverError.value = null
  touched.email = true
  touched.password = true
  if (isRegister.value) {
    touched.name = true
  }

  const result = validateAuthForm(mode.value, form)
  if (!result.valid) {
    fieldErrors.value = result.errors
    return
  }

  fieldErrors.value = {}

  try {
    if (isRegister.value) {
      await authStore.register({
        email: form.email.trim(),
        password: form.password,
        name: form.name.trim() || null,
      })
    } else {
      await authStore.login({
        email: form.email.trim(),
        password: form.password,
      })
    }

    await router.replace(resolvePostAuthTarget())
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      const mappedErrors: AuthFieldErrors = {}
      const emailErr = error.getFieldError('email')
      const passwordErr = error.getFieldError('password')
      const nameErr = error.getFieldError('name')
      if (emailErr) mappedErrors.email = emailErr
      if (passwordErr) mappedErrors.password = passwordErr
      if (nameErr) mappedErrors.name = nameErr

      if (Object.keys(mappedErrors).length > 0) {
        fieldErrors.value = mappedErrors
      }

      serverError.value = {
        status: error.status,
        title: error.title,
        detail: error.detail,
      }
      return
    }

    serverError.value = {
      status: 0,
      title: 'Не удалось выполнить запрос',
      detail: 'Попробуйте повторить попытку через несколько секунд.',
    }
  }
}
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

    <div
      v-if="isMockMode"
      class="border-border bg-surface flex items-center justify-between gap-3 rounded-md border px-4 py-3"
    >
      <div class="flex min-w-0 flex-col gap-0.5">
        <div class="flex items-center gap-1.5">
          <BaseBadge variant="neutral" size="sm">
            <template #icon>
              <Sparkles :size="12" :stroke-width="2" />
            </template>
            Mock API
          </BaseBadge>
          <span class="text-text-secondary truncate text-[12px]">
            {{ DEMO_ACCOUNT_CREDENTIALS.email }}
          </span>
        </div>
        <span class="text-text-muted text-[12px]"> Демо-доступ для проверки без бэкенда </span>
      </div>

      <BaseButton
        variant="secondary"
        size="sm"
        :disabled="authStore.isSubmitting"
        @click="applyDemoCredentials"
      >
        Заполнить
      </BaseButton>
    </div>
  </main>
</template>
