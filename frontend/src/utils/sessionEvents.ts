import { getActivePinia } from 'pinia'

import type { LotSummary } from '@/types/api'

type SessionResetListener = () => void
type LotRemovedListener = (lotIds: ReadonlySet<string>) => void
type LotLifecycleListener = (updated: LotSummary) => void

const FALLBACK_SCOPE = {}
const scopedResetListeners = new WeakMap<object, Map<string, SessionResetListener>>()
const scopedLotRemovedListeners = new WeakMap<object, Map<string, LotRemovedListener>>()
const scopedLotLifecycleListeners = new WeakMap<object, Map<string, LotLifecycleListener>>()
const globalResetListeners = new Map<string, SessionResetListener>()

let lastPiniaRef: WeakRef<object> | null = null

function resolveScopeKey(): object {
  const pinia = getActivePinia()
  if (pinia) {
    lastPiniaRef = typeof WeakRef === 'function' ? new WeakRef(pinia) : null
    return pinia
  }
  return lastPiniaRef?.deref() ?? FALLBACK_SCOPE
}

function registerScopedListener<T>(
  storeMap: WeakMap<object, Map<string, T>>,
  key: string,
  listener: T,
): () => void {
  const scope = resolveScopeKey()
  let entries = storeMap.get(scope)
  if (!entries) {
    entries = new Map<string, T>()
    storeMap.set(scope, entries)
  }
  entries.set(key, listener)
  return () => {
    entries.delete(key)
  }
}

export function onSessionReset(
  key: string,
  listener: SessionResetListener,
  options: { global?: boolean } = {},
): () => void {
  if (options.global) {
    globalResetListeners.set(key, listener)
    return () => {
      globalResetListeners.delete(key)
    }
  }
  return registerScopedListener(scopedResetListeners, key, listener)
}

export function emitSessionReset(): void {
  for (const listener of Array.from(globalResetListeners.values())) {
    listener()
  }
  const scope = resolveScopeKey()
  const entries = scopedResetListeners.get(scope)
  if (!entries) return
  for (const listener of Array.from(entries.values())) {
    listener()
  }
}

export function onLotsRemoved(key: string, listener: LotRemovedListener): () => void {
  return registerScopedListener(scopedLotRemovedListeners, key, listener)
}

export function emitLotsRemoved(lotIds: ReadonlySet<string>): void {
  const scope = resolveScopeKey()
  const entries = scopedLotRemovedListeners.get(scope)
  if (!entries) return
  for (const listener of Array.from(entries.values())) {
    listener(lotIds)
  }
}

export function onLotLifecycleUpdated(key: string, listener: LotLifecycleListener): () => void {
  return registerScopedListener(scopedLotLifecycleListeners, key, listener)
}

export function emitLotLifecycleUpdated(updated: LotSummary): void {
  const scope = resolveScopeKey()
  const entries = scopedLotLifecycleListeners.get(scope)
  if (!entries) return
  for (const listener of Array.from(entries.values())) {
    listener(updated)
  }
}
