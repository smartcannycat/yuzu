import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/api'
import { isSafeRelativePath } from '@/utils/url'
import {
  validateAuthForm,
  validateEmail,
  validateName,
  validatePassword,
  type AuthField,
  type AuthFieldErrors,
  type AuthMode,
} from '@/utils/validation'

export interface AuthServerError {
  status: number
  title: string
  detail: string
}

export function useAuthForm() {
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
  const serverError = ref<AuthServerError | null>(null)
  const demoCredentials = ref<{ email: string; password: string } | null>(null)
  const isMockEnv = import.meta.env.PROD
    ? import.meta.env.VITE_USE_MOCKS === 'true'
    : import.meta.env.VITE_USE_MOCKS !== 'false'

  if (isMockEnv) {
    onMounted(async () => {
      try {
        const { DEMO_ACCOUNT_CREDENTIALS } = await import('@/api/mockApiClient')
        demoCredentials.value = {
          email: DEMO_ACCOUNT_CREDENTIALS.email,
          password: DEMO_ACCOUNT_CREDENTIALS.password,
        }
      } catch {
        // Ignore mock demo hint load errors.
      }
    })
  }

  const isRegister = computed(() => mode.value === 'register')
  const showSwitchToLoginHint = computed(
    () => isRegister.value && serverError.value?.status === 409,
  )

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
    if (!demoCredentials.value) return
    mode.value = 'login'
    form.email = demoCredentials.value.email
    form.password = demoCredentials.value.password
    fieldErrors.value = {}
    serverError.value = null
  }

  function switchToLoginFromConflict(): void {
    mode.value = 'login'
    form.password = ''
  }

  function resolvePostAuthTarget() {
    const redirectParam = route.query.redirect
    if (typeof redirectParam === 'string') {
      const trimmed = redirectParam.trim()
      if (isSafeRelativePath(trimmed)) {
        return trimmed
      }
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

  return {
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
  }
}
