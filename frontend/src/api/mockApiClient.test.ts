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

    const toyotaOnly = await client.lots.list({ make: 'Toyota' })
    expect(toyotaOnly.items).toHaveLength(2)
    expect(toyotaOnly.available_filters.makes.length).toBeGreaterThan(1)
    expect(toyotaOnly.available_filters.models.map((item) => item.value)).toEqual([
      'Corolla Touring',
      'Harrier',
    ])
    expect(toyotaOnly.available_filters.counts_by_verdict).toEqual({
      green: 1,
      yellow: 0,
      red: 1,
    })

    const anomalyOnly = await client.lots.list({ has_anomaly: true })
    expect(anomalyOnly.items.length).toBeGreaterThan(0)
    expect(anomalyOnly.items.every((item) => item.has_anomaly)).toBe(true)
    expect(anomalyOnly.available_filters.counts_by_verdict).toEqual({
      green: 0,
      yellow: 1,
      red: 1,
    })

    const toyotaAnomaly = await client.lots.list({ make: 'Toyota', has_anomaly: true })
    expect(toyotaAnomaly.items).toHaveLength(1)
    expect(toyotaAnomaly.available_filters.counts_by_verdict).toEqual({
      green: 0,
      yellow: 0,
      red: 1,
    })
    expect(toyotaAnomaly.available_filters.models).toEqual([{ value: 'Harrier', count: 1 }])

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

  it('returns detailed lot spec, recalculates economics, and throws 404 for unknown lot', async () => {
    const client = createMockApiClient({ delayMs: 0 })

    const detail = await client.lots.getDetail('892b4e10-3a2c-411f-a801-019283746501')
    expect(detail.passport.make).toBe('Toyota')
    expect(detail.passport.model).toBe('Corolla Touring')
    expect(detail.economics.wise_cost_ladder.steps).toHaveLength(7)
    const stepsSum = detail.economics.wise_cost_ladder.steps.reduce(
      (acc, step) => acc + step.amount_rub,
      0,
    )
    expect(stepsSum).toBe(detail.economics.wise_cost_ladder.turnkey_cost_rub)

    const recalc = await client.lots.recalculate(detail.lot_id, {
      bid_jpy: detail.economics.wise_cost_ladder.car_bid_jpy + 100_000,
      is_commercial_util: true,
      include_repairs: false,
    })
    expect(recalc.is_commercial_util).toBe(true)
    expect(recalc.include_repairs).toBe(false)
    expect(recalc.customs.utilization_fee_rub).toBe(528_000)
    expect(recalc.turnkey_cost_rub).toBeGreaterThan(
      detail.economics.wise_cost_ladder.turnkey_cost_rub,
    )

    await expect(
      client.lots.getDetail('00000000-0000-0000-0000-000000000000'),
    ).rejects.toMatchObject({
      status: 404,
    })
  })

  it('supports lifecycle filtering, manual archive/unarchive without re-expiry, and single/bulk soft-delete', async () => {
    localStorage.clear()
    const client = createMockApiClient({ delayMs: 0 })

    const active = await client.lots.list({ lifecycle: 'active' })
    expect(active.items).toHaveLength(6)
    expect(active.available_filters.archived_lots_count).toBe(2)

    const archived = await client.lots.list({ lifecycle: 'archived' })
    expect(archived.items).toHaveLength(2)
    expect(archived.items.some((item) => item.archived_reason === 'expired')).toBe(true)
    expect(archived.items.some((item) => item.archived_reason === 'manual')).toBe(true)

    const all = await client.lots.list({ lifecycle: 'all' })
    expect(all.items).toHaveLength(8)

    // Unarchiving an expired lot suppresses automatic re-archival
    const expiredLot = archived.items.find((item) => item.archived_reason === 'expired')!
    const restored = await client.lots.updateLifecycle(expiredLot.lot_id, { is_archived: false })
    expect(restored.is_archived).toBe(false)
    expect(restored.archived_reason).toBeNull()
    expect(restored.expires_at).toBeNull()

    const activeAfterRestore = await client.lots.list({ lifecycle: 'active' })
    expect(activeAfterRestore.items.some((item) => item.lot_id === expiredLot.lot_id)).toBe(true)
    expect(activeAfterRestore.available_filters.archived_lots_count).toBe(1)

    // Manual archive + single soft-delete + 404 afterwards
    const manualArchived = await client.lots.updateLifecycle(expiredLot.lot_id, {
      is_archived: true,
    })
    expect(manualArchived.is_archived).toBe(true)
    expect(manualArchived.archived_reason).toBe('manual')

    await expect(client.lots.deleteLot(expiredLot.lot_id)).resolves.toBeUndefined()
    await expect(client.lots.getDetail(expiredLot.lot_id)).rejects.toMatchObject({ status: 404 })
    await expect(client.lots.deleteLot(expiredLot.lot_id)).rejects.toMatchObject({ status: 404 })

    // Bulk soft-delete removes multiple remaining active lots
    const bulkTargets = activeAfterRestore.items
      .filter((item) => item.lot_id !== expiredLot.lot_id)
      .slice(0, 2)
      .map((item) => item.lot_id)

    const bulkRes = await client.lots.bulkDeleteLots({ lot_ids: bulkTargets })
    expect(bulkRes.deleted_ids).toEqual(bulkTargets)

    const remainingAll = await client.lots.list({ lifecycle: 'all' })
    for (const id of bulkTargets) {
      expect(remainingAll.items.some((item) => item.lot_id === id)).toBe(false)
    }
  })
})
