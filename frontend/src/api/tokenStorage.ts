import { ref } from 'vue'

import type { AuthTokensResponse, UserProfileResponse } from '@/types/api'
import { emitSessionReset } from '@/utils/sessionEvents'

export const AUTH_BROADCAST_CHANNEL_NAME = 'yuzu.auth'
export const AUTH_SYNC_STORAGE_KEY = 'yuzu.auth.sync'

export interface StoredSession {
  accessToken: string
  user: UserProfileResponse
}

export type AuthSyncMessage =
  | { type: 'logout'; senderId: string; timestamp: number }
  | { type: 'account-switch'; senderId: string; userId: string; timestamp: number }

type SessionChangeListener = (reason: 'login' | 'refresh' | 'logout' | 'cross-tab') => void

const TAB_INSTANCE_ID =
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `tab-${Math.random().toString(36).slice(2, 10)}`

const session = ref<StoredSession | null>(null)
let sessionGen = 0
const sessionChangeListeners = new Set<SessionChangeListener>()

let broadcastChannel: BroadcastChannel | null = null
let isCrossTabInitialized = false

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseAuthSyncMessage(raw: unknown): AuthSyncMessage | null {
  if (!isPlainRecord(raw)) return null
  if (typeof raw.senderId !== 'string' || typeof raw.timestamp !== 'number') return null

  if (raw.type === 'logout') {
    return {
      type: 'logout',
      senderId: raw.senderId,
      timestamp: raw.timestamp,
    }
  }

  if (raw.type === 'account-switch' && typeof raw.userId === 'string' && raw.userId.length > 0) {
    return {
      type: 'account-switch',
      senderId: raw.senderId,
      userId: raw.userId,
      timestamp: raw.timestamp,
    }
  }

  return null
}

function notifySessionChange(reason: 'login' | 'refresh' | 'logout' | 'cross-tab'): void {
  for (const listener of Array.from(sessionChangeListeners)) {
    listener(reason)
  }
}

function applyRemoteSyncMessage(message: AuthSyncMessage): void {
  if (message.senderId === TAB_INSTANCE_ID) return

  if (message.type === 'logout') {
    if (session.value !== null) {
      sessionGen += 1
      session.value = null
      emitSessionReset()
      notifySessionChange('cross-tab')
    }
    return
  }

  if (message.type === 'account-switch') {
    const currentUserId = session.value?.user.user_id
    if (currentUserId && currentUserId !== message.userId) {
      sessionGen += 1
      session.value = null
      emitSessionReset()
      notifySessionChange('cross-tab')
    }
  }
}

function handleStorageEvent(event: StorageEvent): void {
  if (event.key !== AUTH_SYNC_STORAGE_KEY || !event.newValue) return
  try {
    const parsed = parseAuthSyncMessage(JSON.parse(event.newValue))
    if (parsed) {
      applyRemoteSyncMessage(parsed)
    }
  } catch {
    // Ignore malformed cross-tab sync payloads.
  }
}

function ensureCrossTabSyncInitialized(): void {
  if (isCrossTabInitialized || typeof window === 'undefined') return
  isCrossTabInitialized = true

  if (typeof BroadcastChannel === 'function') {
    try {
      broadcastChannel = new BroadcastChannel(AUTH_BROADCAST_CHANNEL_NAME)
      broadcastChannel.onmessage = (event: MessageEvent<unknown>) => {
        const parsed = parseAuthSyncMessage(event.data)
        if (parsed) {
          applyRemoteSyncMessage(parsed)
        }
      }
    } catch {
      broadcastChannel = null
    }
  }

  window.addEventListener('storage', handleStorageEvent)
}

function postCrossTabMessage(message: AuthSyncMessage): void {
  ensureCrossTabSyncInitialized()

  if (broadcastChannel) {
    try {
      broadcastChannel.postMessage(message)
      return
    } catch {
      // Fall through to token-free StorageEvent ping if channel is closed.
    }
  }

  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(AUTH_SYNC_STORAGE_KEY, JSON.stringify(message))
  } catch {
    // Ignore storage quota / private-mode restrictions.
  }
}

ensureCrossTabSyncInitialized()

export const tokenStorage = {
  session,

  getSessionGen(): number {
    return sessionGen
  },

  getSession(): StoredSession | null {
    return session.value
  },

  getAccessToken(): string | null {
    return session.value?.accessToken ?? null
  },

  getUser(): UserProfileResponse | null {
    return session.value?.user ?? null
  },

  setFromAuthResponse(
    response: AuthTokensResponse,
    options: { isNewSession?: boolean } = {},
  ): void {
    session.value = {
      accessToken: response.access_token,
      user: response.user,
    }
    if (options.isNewSession) {
      postCrossTabMessage({
        type: 'account-switch',
        senderId: TAB_INSTANCE_ID,
        userId: response.user.user_id,
        timestamp: Date.now(),
      })
      notifySessionChange('login')
    } else {
      notifySessionChange('refresh')
    }
  },

  setUser(user: UserProfileResponse): void {
    if (!session.value) return
    session.value = {
      ...session.value,
      user,
    }
  },

  resetSession(options: { broadcastLogout?: boolean } = {}): number {
    sessionGen += 1
    session.value = null
    emitSessionReset()
    if (options.broadcastLogout) {
      postCrossTabMessage({
        type: 'logout',
        senderId: TAB_INSTANCE_ID,
        timestamp: Date.now(),
      })
    }
    notifySessionChange('logout')
    return sessionGen
  },

  clear(options: { broadcast?: boolean } = {}): void {
    this.resetSession({ broadcastLogout: options.broadcast })
  },

  onSessionChange(listener: SessionChangeListener): () => void {
    sessionChangeListeners.add(listener)
    return () => {
      sessionChangeListeners.delete(listener)
    }
  },
}
