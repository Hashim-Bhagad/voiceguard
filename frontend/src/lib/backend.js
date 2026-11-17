import { useSyncExternalStore } from 'react'
import { API_BASE } from './analysis'

// The Agent37 backend sleeps when idle; the first request wakes it and loads the
// model (10-30 s). Nothing wakes it on page load: sample calls never need it, and an
// idle visitor shouldn't spin up a machine. It wakes on intent instead (opening the
// Upload or Record tab, pointing at the drop zone or a record button, dragging a file
// in), which gives the model a head start while the person picks a file.
// One shared probe tells every screen whether it is ready.
//   status: 'idle' (asleep, not asked yet) | 'waking' | 'ready' | 'offline'
let state = { status: 'idle', model: null, since: Date.now() }
const listeners = new Set()
const emit = next => { state = { ...state, ...next }; listeners.forEach(l => l()) }

let inflight = null
export function wakeBackend() {
  if (inflight || state.status === 'ready') return inflight
  // After a failed wake, let the next intent retry, but not on every hover.
  if (state.status === 'offline' && Date.now() - state.since < 15000) return null
  emit({ status: 'waking', since: Date.now() })
  inflight = fetch(`${API_BASE}/api/v1/health`, { cache: 'no-store', signal: AbortSignal.timeout(60000) })
    .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
    .then(body => emit({ status: 'ready', model: body?.model_ver || null }))
    .catch(() => emit({ status: 'offline', since: Date.now() }))
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
