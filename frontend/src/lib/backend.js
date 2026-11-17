import { useSyncExternalStore } from 'react'
import { API_BASE } from './analysis'

// The Agent37 backend sleeps when idle; the first request wakes it and loads the
// model (10-30 s). One shared probe tells every screen whether it is ready, so the
// UI can say "warming up" honestly instead of looking frozen.
//   status: 'idle' | 'waking' | 'ready' | 'offline'
let state = { status: 'idle', model: null, since: Date.now() }
const listeners = new Set()
const emit = next => { state = { ...state, ...next }; listeners.forEach(l => l()) }

let inflight = null
export function wakeBackend() {
  if (inflight || state.status === 'ready') return inflight
  emit({ status: 'waking', since: Date.now() })
  inflight = fetch(`${API_BASE}/api/v1/health`, { cache: 'no-store', signal: AbortSignal.timeout(60000) })
    .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
    .then(body => emit({ status: 'ready', model: body?.model_ver || null }))
    .catch(() => emit({ status: 'offline' }))
    .finally(() => { inflight = null })
  return inflight
}

export function markBackendReady() { if (state.status !== 'ready') emit({ status: 'ready' }) }

export function useBackend() {
  return useSyncExternalStore(
    cb => { listeners.add(cb); return () => listeners.delete(cb) },
    () => state,
  )
}
