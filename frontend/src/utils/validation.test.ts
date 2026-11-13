import { beforeEach, describe, expect, it } from 'vitest'

import {
  NAME_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  validateAuthForm,
  validateEmail,
  validateName,
  validatePassword,
} from '@/utils/validation'

describe('auth validation', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('validates email format and emptiness', () => {
    expect(validateEmail('')).toBe('Введите email')
    expect(validateEmail('   ')).toBe('Введите email')
    expect(validateEmail('invalid-email')).toBe('Укажите корректный email')
    expect(validateEmail('alex@example.com')).toBeUndefined()
  })

  it('validates password rules differently for login and register', () => {
    expect(validatePassword('', 'login')).toBe('Введите пароль')
    expect(validatePassword('123', 'login')).toBeUndefined()

    expect(validatePassword('1234567', 'register')).toBe(`Минимум ${PASSWORD_MIN_LENGTH} символов`)
    expect(validatePassword('12345678', 'register')).toBeUndefined()
    expect(validatePassword('a'.repeat(PASSWORD_MAX_LENGTH + 1), 'register')).toBe(
      `Максимум ${PASSWORD_MAX_LENGTH} символов`,
    )
  })

  it('validates optional name length', () => {
    expect(validateName('')).toBeUndefined()
    expect(validateName('Алексей')).toBeUndefined()
    expect(validateName('А'.repeat(NAME_MAX_LENGTH + 1))).toBe(
      `Имя не должно превышать ${NAME_MAX_LENGTH} символов`,
    )
  })

  it('aggregates errors in validateAuthForm', () => {
    const invalidRegister = validateAuthForm('register', {
      email: 'bad',
      password: 'short',
      name: 'А'.repeat(NAME_MAX_LENGTH + 1),
    })
    expect(invalidRegister.valid).toBe(false)
    expect(invalidRegister.errors.email).toBeDefined()
    expect(invalidRegister.errors.password).toBeDefined()
    expect(invalidRegister.errors.name).toBeDefined()

    const validLogin = validateAuthForm('login', {
      email: 'alex@example.com',
      password: 'secret',
      name: '',
    })
    expect(validLogin.valid).toBe(true)
    expect(validLogin.errors).toEqual({})
  })
})
