import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createHttpApiClient, setHttpUnauthorizedHandler } from '@/api/httpClient'
import { tokenStorage } from '@/api/tokenStorage'
import { ApiError, type AuthTokensResponse, type UserProfileResponse } from '@/types/api'

const sampleUser: UserProfileResponse = {
  user_id: '11111111-2222-4333-8444-555555555555',
  email: 'alex@example.com',
  name: 'Алексей',
  created_at: '2026-11-13T08:00:00Z',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function extractUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return input.url
}

function extractAuthHeader(input: RequestInfo | URL, init?: RequestInit): string | null {
  if (init?.headers) {
    return new Headers(init.headers).get('Authorization')
  }
  if (input instanceof Request) {
    return input.headers.get('Authorization')
  }
  return null
}

describe('httpClient (ofetch)', () => {
  beforeEach(() => {
    tokenStorage.clear()
    window.localStorage.clear()
    setHttpUnauthorizedHandler(null)
  })

  afterEach(() => {
    setHttpUnauthorizedHandler(null)
    vi.restoreAllMocks()
  })

  it('attaches Bearer token and returns user profile', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(extractUrl(input)).toBe('/api/v1/auth/me')
      expect(extractAuthHeader(input, init)).toBe('Bearer access-1')
      return jsonResponse(sampleUser, 200)
    })

    const client = createHttpApiClient({ fetch: fetchMock })
    const profile = await client.auth.me()
    expect(profile).toEqual(sampleUser)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('performs single-flight refresh on 401 and retries concurrent requests', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'expired-access',
      refresh_token: 'valid-refresh',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    let refreshCalls = 0
    const refreshedTokens: AuthTokensResponse = {
      access_token: 'fresh-access',
      refresh_token: 'fresh-refresh',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    }

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = extractUrl(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1
        return jsonResponse(refreshedTokens, 200)
      }

      const authHeader = extractAuthHeader(input, init)
      if (authHeader === 'Bearer expired-access') {
        return jsonResponse(
          {
            type: 'about:blank',
            title: 'Токен истек',
            status: 401,
            detail: 'Access token expired',
          },
          401,
        )
      }

      expect(authHeader).toBe('Bearer fresh-access')
      return jsonResponse(sampleUser, 200)
    })

    const client = createHttpApiClient({ fetch: fetchMock })
    const [first, second] = await Promise.all([client.auth.me(), client.auth.me()])

    expect(first).toEqual(sampleUser)
    expect(second).toEqual(sampleUser)
    expect(refreshCalls).toBe(1)
    expect(tokenStorage.getAccessToken()).toBe('fresh-access')
    expect(tokenStorage.getRefreshToken()).toBe('fresh-refresh')
  })

  it('clears session and notifies unauthorized handler when refresh fails', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'expired-access',
      refresh_token: 'dead-refresh',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    const onUnauthorized = vi.fn()
    setHttpUnauthorizedHandler(onUnauthorized)

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = extractUrl(input)
      if (url.endsWith('/auth/refresh')) {
        return jsonResponse(
          {
            type: 'about:blank',
            title: 'Сессия истекла',
            status: 401,
            detail: 'Refresh token invalid',
          },
          401,
        )
      }
      return jsonResponse(
        {
          type: 'about:blank',
          title: 'Требуется авторизация',
          status: 401,
          detail: 'Unauthorized',
        },
        401,
      )
    })

    const client = createHttpApiClient({ fetch: fetchMock })
    await expect(client.auth.me()).rejects.toBeInstanceOf(ApiError)
    expect(tokenStorage.getSession()).toBeNull()
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('reuses refreshed token for staggered 401s and avoids duplicate refresh', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'expired-access',
      refresh_token: 'valid-refresh',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    let refreshCalls = 0
    let releaseSecondInitialResponse!: () => void
    const secondInitialGate = new Promise<void>((resolve) => {
      releaseSecondInitialResponse = resolve
    })
    let meCalls = 0

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = extractUrl(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1
        return jsonResponse(
          {
            access_token: 'fresh-access',
            refresh_token: 'fresh-refresh',
            token_type: 'bearer',
            expires_in_sec: 3600,
            user: sampleUser,
          } satisfies AuthTokensResponse,
          200,
        )
      }

      const authHeader = extractAuthHeader(input, init)
      if (authHeader === 'Bearer expired-access') {
        meCalls += 1
        if (meCalls === 2) {
          await secondInitialGate
        }
        return jsonResponse({ title: 'Expired', status: 401, detail: 'Expired' }, 401)
      }

      expect(authHeader).toBe('Bearer fresh-access')
      return jsonResponse(sampleUser, 200)
    })

    const client = createHttpApiClient({ fetch: fetchMock })
    const firstPromise = client.auth.me()
    const secondPromise = client.auth.me()

    const first = await firstPromise
    releaseSecondInitialResponse()
    const second = await secondPromise

    expect(first).toEqual(sampleUser)
    expect(second).toEqual(sampleUser)
    expect(refreshCalls).toBe(1)
  })

  it('clears session if retried request after refresh still returns 401', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'expired-access',
      refresh_token: 'valid-refresh',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    const onUnauthorized = vi.fn()
    setHttpUnauthorizedHandler(onUnauthorized)

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = extractUrl(input)
      if (url.endsWith('/auth/refresh')) {
        return jsonResponse(
          {
            access_token: 'rejected-access',
            refresh_token: 'fresh-refresh',
            token_type: 'bearer',
            expires_in_sec: 3600,
            user: sampleUser,
          } satisfies AuthTokensResponse,
          200,
        )
      }
      return jsonResponse({ title: 'Revoked', status: 401, detail: 'Revoked' }, 401)
    })

    const client = createHttpApiClient({ fetch: fetchMock })
    await expect(client.auth.me()).rejects.toBeInstanceOf(ApiError)
    expect(tokenStorage.getSession()).toBeNull()
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('parses RFC 7807 ProblemDetail with invalid_params', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        {
          type: 'https://api.auction-calc.ru/errors/validation-error',
          title: 'Ошибка валидации параметров',
          status: 422,
          detail: 'Пароль слишком короткий',
          instance: '/api/v1/auth/register',
          invalid_params: [
            {
              name: 'password',
              reason: 'Минимум 8 символов',
            },
          ],
        },
        422,
      ),
    )

    const client = createHttpApiClient({ fetch: fetchMock })
    let caught: unknown
    try {
      await client.auth.register({
        email: 'alex@example.com',
        password: '123',
      })
    } catch (error: unknown) {
      caught = error
    }

    expect(caught).toBeInstanceOf(ApiError)
    const apiError = caught as ApiError
    expect(apiError.status).toBe(422)
    expect(apiError.title).toBe('Ошибка валидации параметров')
    expect(apiError.getFieldError('password')).toBe('Минимум 8 символов')
  })

  it('requests lots feed with cleaned query parameters and auth header', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'access-lots',
      refresh_token: 'refresh-lots',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = extractUrl(input)
      expect(url).toContain('/api/v1/lots?')
      expect(url).toContain('query=Corolla')
      expect(url).toContain('verdict=green')
      expect(url).toContain('has_anomaly=true')
      expect(url).not.toContain('make=')
      expect(extractAuthHeader(input, init)).toBe('Bearer access-lots')

      return jsonResponse({
        items: [],
        in_progress: {
          active_batches_count: 0,
          total_processing_lots: 0,
          items: [],
        },
        pagination: {
          total_items: 0,
          page: 1,
          page_size: 20,
          total_pages: 0,
        },
        available_filters: {
          total_lots_count: 0,
          archived_lots_count: 0,
          makes: [],
          models: [],
          counts_by_verdict: {},
        },
      })
    })

    const client = createHttpApiClient({ fetch: fetchMock })
    const result = await client.lots.list({
      query: '  Corolla ',
      make: '   ',
      verdict: 'green',
      has_anomaly: true,
    })

    expect(result.items).toEqual([])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('sends multipart FormData for createBatch and appendBatchItems and polls batch status', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'access-batch',
      refresh_token: 'refresh-batch',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = extractUrl(input)
      expect(extractAuthHeader(input, init)).toBe('Bearer access-batch')

      if (url === '/api/v1/lots/batches') {
        expect(init?.method).toBe('POST')
        if (!(init?.body instanceof FormData)) {
          throw new Error('Expected FormData body')
        }
        const files = init.body.getAll('files')
        expect(files).toHaveLength(2)
        return jsonResponse(
          {
            batch_id: 'batch-uuid-1',
            total_items: 2,
            status: 'queued',
            created_at: '2026-11-13T10:15:00Z',
            poll_interval_ms: 1500,
          },
          202,
        )
      }

      if (url === '/api/v1/lots/batches/batch-uuid-1') {
        expect(init?.method).toBe('GET')
        return jsonResponse({
          batch_id: 'batch-uuid-1',
          status: 'processing',
          mascot: {
            mood: 'thinking',
            phrase_ru: 'Распознаем лоты... 1/2',
            badge_text: '1 из 2 готово',
          },
          total_count: 2,
          processed_count: 1,
          ready_count: 1,
          failed_count: 0,
          items: [],
        })
      }

      expect(url).toBe('/api/v1/lots/batches/batch-uuid-1/items')
      expect(init?.method).toBe('POST')
      expect(init?.body).toBeInstanceOf(FormData)
      return jsonResponse(
        {
          batch_id: 'batch-uuid-1',
          status: 'processing',
          mascot: {
            mood: 'thinking',
            phrase_ru: 'Распознаем лоты... 1/3',
            badge_text: '1 из 3 готово',
          },
          total_count: 3,
          processed_count: 1,
          ready_count: 1,
          failed_count: 0,
          items: [],
        },
        202,
      )
    })

    const client = createHttpApiClient({ fetch: fetchMock })
    const fileA = new File(['a'], 'a.jpg', { type: 'image/jpeg' })
    const fileB = new File(['b'], 'b.png', { type: 'image/png' })
    const fileC = new File(['c'], 'c.webp', { type: 'image/webp' })

    const created = await client.lots.createBatch([fileA, fileB])
    expect(created.batch_id).toBe('batch-uuid-1')

    const progress = await client.lots.getBatch('batch-uuid-1')
    expect(progress.total_count).toBe(2)

    const appended = await client.lots.appendBatchItems('batch-uuid-1', [fileC])
    expect(appended.total_count).toBe(3)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('sends lifecycle query and calls PATCH, DELETE, and POST bulk-delete lot endpoints', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'access-lifecycle',
      refresh_token: 'refresh-lifecycle',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: sampleUser,
    })

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = extractUrl(input)
      const method = init?.method ?? 'GET'

      if (url.startsWith('/api/v1/lots?')) {
        expect(url).toContain('lifecycle=archived')
        return jsonResponse({
          items: [],
          in_progress: { active_batches_count: 0, total_processing_lots: 0, items: [] },
          pagination: { total_items: 0, page: 1, page_size: 20, total_pages: 0 },
          available_filters: {
            total_lots_count: 0,
            archived_lots_count: 2,
            makes: [],
            models: [],
            counts_by_verdict: {},
          },
        })
      }

      if (url === '/api/v1/lots/lot-42' && method === 'PATCH') {
        expect(JSON.parse(String(init?.body))).toEqual({ is_archived: true })
        return jsonResponse({
          lot_id: 'lot-42',
          make: 'Toyota',
          model: 'Corolla',
          year: 2021,
          engine_cc: 1797,
          frame_id: 'ZWE211-1234567',
          auction_house: 'USS',
          lot_number: '1001',
          overall_grade: '4.5',
          mileage_km: 32000,
          turnkey_cost_rub: 1850000,
          market_price_rf_rub: 2150000,
          verdict: 'green',
          verdict_headline: 'Хороший лот',
          net_benefit_rub: 300000,
          meti_sanction_risk: false,
          has_anomaly: false,
          anomaly_text: null,
          thumbnail_url: null,
          auction_date: null,
          is_archived: true,
          archived_at: '2026-11-13T10:00:00Z',
          archived_reason: 'manual',
          expires_at: null,
          created_at: '2026-11-10T10:00:00Z',
        })
      }

      if (url === '/api/v1/lots/lot-42' && method === 'DELETE') {
        return new Response(null, { status: 204 })
      }

      expect(url).toBe('/api/v1/lots/bulk-delete')
      expect(method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({ lot_ids: ['lot-1', 'lot-2'] })
      return jsonResponse({
        deleted_ids: ['lot-1', 'lot-2'],
        not_found_ids: [],
        deleted_count: 2,
      })
    })

    const client = createHttpApiClient({ fetch: fetchMock })

    const listRes = await client.lots.list({ lifecycle: 'archived' })
    expect(listRes.available_filters.archived_lots_count).toBe(2)

    const patched = await client.lots.updateLifecycle('lot-42', { is_archived: true })
    expect(patched.is_archived).toBe(true)
    expect(patched.archived_reason).toBe('manual')

    await expect(client.lots.deleteLot('lot-42')).resolves.toBeUndefined()

    const bulkRes = await client.lots.bulkDeleteLots({ lot_ids: ['lot-1', 'lot-2'] })
    expect(bulkRes.deleted_ids).toEqual(['lot-1', 'lot-2'])
    expect(fetchMock).toHaveBeenCalledTimes(4)
  })
})
