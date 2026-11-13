export type AuthMode = 'login' | 'register'
export type AuthField = 'email' | 'password' | 'name'

export interface AuthFormValues {
  email: string
  password: string
  name: string
}

export type AuthFieldErrors = Partial<Record<AuthField, string>>

export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128
export const NAME_MAX_LENGTH = 100

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateEmail(rawValue: string): string | undefined {
  const email = rawValue.trim()
  if (!email) {
    return 'Введите email'
  }
  if (!EMAIL_PATTERN.test(email)) {
    return 'Укажите корректный email'
  }
  return undefined
}

export function validatePassword(rawValue: string, mode: AuthMode): string | undefined {
  if (!rawValue) {
    return 'Введите пароль'
  }
  if (mode === 'register') {
    if (rawValue.length < PASSWORD_MIN_LENGTH) {
      return `Минимум ${PASSWORD_MIN_LENGTH} символов`
    }
    if (rawValue.length > PASSWORD_MAX_LENGTH) {
      return `Максимум ${PASSWORD_MAX_LENGTH} символов`
    }
  }
  return undefined
}

export function validateName(rawValue: string): string | undefined {
  const trimmed = rawValue.trim()
  if (trimmed.length > NAME_MAX_LENGTH) {
    return `Имя не должно превышать ${NAME_MAX_LENGTH} символов`
  }
  return undefined
}

export function validateAuthForm(
  mode: AuthMode,
  values: AuthFormValues,
): { valid: boolean; errors: AuthFieldErrors } {
  const errors: AuthFieldErrors = {}

  const emailError = validateEmail(values.email)
  if (emailError) errors.email = emailError

  const passwordError = validatePassword(values.password, mode)
  if (passwordError) errors.password = passwordError

  if (mode === 'register') {
    const nameError = validateName(values.name)
    if (nameError) errors.name = nameError
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  }
}
