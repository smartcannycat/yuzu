import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { DEMO_ACCOUNT_CREDENTIALS } from '@/api/mockApiClient'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/api'
import AuthView from '@/views/AuthView.vue'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('AuthView', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null
  let pinia: ReturnType<typeof createPinia>

  beforeAll(async () => {
    await import('@/api/mockApiClient')
  })

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
  })

  async function mountAuth(initialPath = '/auth') {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        { path: '/lots/:lotId', name: 'lot-detail', component: { template: '<div />' } },
        { path: '/auth', name: 'auth', component: AuthView },
        { path: '/login', name: 'login', component: AuthView },
        { path: '/register', name: 'register', component: AuthView },
      ],
    })
    await router.push(initialPath)
    await router.isReady()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(AuthView)
    app.use(pinia)
    app.use(router)
    app.mount(host)
    await flushUi()

    return { host, router, authStore: useAuthStore() }
  }

  it('validates fields on submit, supports demo autofill, and redirects safely after login', async () => {
    const { host, router, authStore } = await mountAuth('/auth?redirect=%2Flots%2F123')
    const replaceSpy = vi.spyOn(router, 'replace')
    const loginSpy = vi.spyOn(authStore, 'login').mockResolvedValue({
      user_id: 'u1',
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      name: 'Demo',
      created_at: '2026-11-10T00:00:00Z',
    })

    const form = host.querySelector('form') as HTMLFormElement
    form.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushUi()
    expect(loginSpy).not.toHaveBeenCalled()
    expect(host.textContent).toContain('Введите email')

    await vi.waitFor(() => {
      const demoBtn = Array.from(host.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Заполнить'),
      )
      expect(demoBtn).toBeTruthy()
    })
    const demoBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Заполнить'),
    )!
    demoBtn.click()
    await flushUi()

    form.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushUi()

    expect(loginSpy).toHaveBeenCalledWith({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })
    expect(replaceSpy).toHaveBeenCalledWith('/lots/123')
  })

  it('rejects unsafe external redirect targets and falls back to home', async () => {
    const { host, router, authStore } = await mountAuth('/auth?redirect=https://evil.example')
    const replaceSpy = vi.spyOn(router, 'replace')
    vi.spyOn(authStore, 'login').mockResolvedValue({
      user_id: 'u1',
      email: 'alex@example.com',
      name: 'Alex',
      created_at: '2026-11-10T00:00:00Z',
    })

    const emailInput = host.querySelector('input[type="email"]') as HTMLInputElement
    const passwordInput = host.querySelector('input[type="password"]') as HTMLInputElement
    emailInput.value = 'alex@example.com'
    emailInput.dispatchEvent(new Event('input'))
    passwordInput.value = 'Password123!'
    passwordInput.dispatchEvent(new Event('input'))
    await flushUi()

    const form = host.querySelector('form') as HTMLFormElement
    form.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushUi()

    expect(replaceSpy).toHaveBeenCalledWith({ name: 'home' })
  })

  it('switches to register mode, renders 409 conflict hint, and toggles back to login', async () => {
    const { host, authStore } = await mountAuth('/auth?mode=register')
    expect(host.textContent).toContain('Создать аккаунт')

    vi.spyOn(authStore, 'register').mockRejectedValue(
      new ApiError({
        type: 'about:blank',
        title: 'Аккаунт уже существует',
        status: 409,
        detail: 'Пользователь с таким email уже зарегистрирован.',
        invalid_params: [{ name: 'email', reason: 'Email уже занят' }],
      }),
    )

    const emailInput = host.querySelector('input[type="email"]') as HTMLInputElement
    const passwordInput = host.querySelector('input[type="password"]') as HTMLInputElement
    emailInput.value = 'taken@example.com'
    emailInput.dispatchEvent(new Event('input'))
    passwordInput.value = 'Password123!'
    passwordInput.dispatchEvent(new Event('input'))
    await flushUi()

    const form = host.querySelector('form') as HTMLFormElement
    form.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushUi()

    const alert = host.querySelector('[role="alert"]')
    expect(alert?.textContent).toContain('Аккаунт уже существует')
    expect(host.textContent).toContain('Email уже занят')

    const switchBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Перейти ко входу с этим email'),
    )
    expect(switchBtn).toBeTruthy()
    switchBtn!.click()
    await flushUi()

    expect(host.textContent).toContain('Вход в аккаунт')
    expect(passwordInput.value).toBe('')
  })
})
