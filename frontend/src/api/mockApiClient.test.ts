import { beforeEach, describe, expect, it } from 'vitest'

import { createMockApiClient, DEMO_ACCOUNT_CREDENTIALS, resetMockUsers } from '@/api/mockApiClient'
import { tokenStorage } from '@/api/tokenStorage'
import { ApiError } from '@/types/api'

describe('mockApiClient', () => {
  beforeEach(() => {
    tokenStorage.clear()
    resetMockUsers()
    window.localStorage.clear()
  })

  it('logs in with seeded demo user and resolves me()', async () => {
    const client = createMockApiClient({ delayMs: 0 })
    const tokens = await client.auth.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })

    expect(tokens.token_type).toBe('bearer')
    expect(tokens.user.email).toBe(DEMO_ACCOUNT_CREDENTIALS.email)

    tokenStorage.setFromAuthResponse(tokens)
    const me = await client.auth.me()
    expect(me.email).toBe(DEMO_ACCOUNT_CREDENTIALS.email)
  })

  it('throws 401 on invalid login credentials', async () => {
    const client = createMockApiClient({ delayMs: 0 })
    await expect(
      client.auth.login({
        email: DEMO_ACCOUNT_CREDENTIALS.email,
        password: 'wrong-password',
      }),
    ).rejects.toMatchObject({
      status: 401,
    })
  })

  it('registers a new user and rejects duplicate email with 409 Conflict', async () => {
    const client = createMockApiClient({ delayMs: 0 })

    const registered = await client.auth.register({
      email: 'newuser@example.com',
      password: 'password123',
      name: 'Мария',
    })
    expect(registered.user.email).toBe('newuser@example.com')
    expect(registered.user.name).toBe('Мария')

    let duplicateError: unknown
    try {
      await client.auth.register({
        email: 'newuser@example.com',
        password: 'password123',
      })
    } catch (error: unknown) {
      duplicateError = error
    }

    expect(duplicateError).toBeInstanceOf(ApiError)
    expect((duplicateError as ApiError).status).toBe(409)
  })

  it('rejects short password on register with 422 ProblemDetail', async () => {
    const client = createMockApiClient({ delayMs: 0 })

    let validationError: unknown
    try {
      await client.auth.register({
        email: 'short@example.com',
        password: '123',
      })
    } catch (error: unknown) {
      validationError = error
    }

    expect(validationError).toBeInstanceOf(ApiError)
    const apiError = validationError as ApiError
    expect(apiError.status).toBe(422)
    expect(apiError.getFieldError('password')).toBeDefined()
  })
})
