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

  it('lists lots with filtering, sorting, pagination, and available_filters', async () => {
    const client = createMockApiClient({ delayMs: 0 })

    const all = await client.lots.list()
    expect(all.items.length).toBe(6)
    expect(all.available_filters.total_lots_count).toBe(6)
    expect(all.in_progress.total_processing_lots).toBe(2)

    const filtered = await client.lots.list({
      query: 'ZWE211',
      verdict: 'green',
    })
    expect(filtered.items).toHaveLength(1)
    expect(filtered.items[0]?.model).toBe('Corolla Touring')

    const anomalyOnly = await client.lots.list({ has_anomaly: true })
    expect(anomalyOnly.items.length).toBeGreaterThan(0)
    expect(anomalyOnly.items.every((item) => item.has_anomaly)).toBe(true)

    const sortedByBenefit = await client.lots.list({
      sort_by: 'net_benefit',
      sort_order: 'desc',
      page_size: 2,
      page: 1,
    })
    expect(sortedByBenefit.items).toHaveLength(2)
    expect(sortedByBenefit.pagination.total_pages).toBe(3)
    expect(sortedByBenefit.items[0]!.net_benefit_rub).toBeGreaterThanOrEqual(
      sortedByBenefit.items[1]!.net_benefit_rub,
    )
  })
})
