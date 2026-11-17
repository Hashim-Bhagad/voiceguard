import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { demoAnalysis, normalizeAnalysis, request } from './analysis'
import { markBackendReady, wakeBackend } from './backend'

const AnalysisContext = createContext(null)
const HISTORY_KEY = 'tv-history'

function loadHistory() {
  try {
    const rows = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    return Array.isArray(rows) ? rows.slice(0, 50) : []
  } catch {
    return []
  }
}

// Each failure gets its own kind so the UI can offer the one action that helps.
function classify(err) {
  if (err?.name === 'TimeoutError') return { kind: 'timeout', message: 'The service took too long to answer. It may still be waking up.' }
  if (err?.message === 'Failed to fetch') return { kind: 'offline', message: 'The analysis service could not be reached.' }
  if (/returned \d{3}/.test(err?.message || '')) return { kind: 'server', message: err.message }
  return { kind: 'input', message: err?.message || 'Something went wrong with this recording.' }
}

export function AnalysisProvider({ children }) {
  const [status, setStatus] = useState('idle')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [startedAt, setStartedAt] = useState(null)
  const [history, setHistory] = useState(loadHistory)
  const pending = useRef(null)
  const lastInput = useRef(null)

  useEffect(() => () => pending.current?.abort(), [])
  useEffect(() => {
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 50))) } catch { /* private mode */ }
  }, [history])

  const runAnalysis = useCallback(async (input, options = {}) => {
    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller
    lastInput.current = { input, options }
    setStatus('analyzing'); setError(null); setData(null); setStartedAt(Date.now())
    try {
      let result
      if (typeof input === 'string') {
        // Prepared scenarios resolve after a short, honest pause so the pipeline
        // steps are readable; the result is labelled as a demo everywhere.
        await new Promise(r => setTimeout(r, options.instant ? 0 : 1400))
        result = demoAnalysis(input)
      } else {
        if (!(input instanceof Blob) || input.size === 0) throw new Error('Choose a non-empty audio recording.')
        wakeBackend() // no-op if already awake; keeps the status pill honest
        if (input.size > 25 * 1024 * 1024) throw new Error('Please use a recording smaller than 25 MB.')
        const form = new FormData()
        const extension = input.type.includes('mp4') ? 'm4a' : input.type.includes('ogg') ? 'ogg' : input.type.includes('webm') ? 'webm' : 'wav'
        form.append('file', input, input.name || `recording.${extension}`)
        form.append('policy_profile', options.policy || 'standard')
        form.append('lang_hint', options.lang === 'auto-hinglish' ? 'auto' : options.lang || 'auto')
        result = normalizeAnalysis(
          await request('/api/v1/verify/file', { method: 'POST', body: form, signal: controller.signal }),
          input.name || 'Microphone recording',
        )
        markBackendReady()
      }
      if (controller.signal.aborted) return
      setData(result); setStatus('complete')
      // The landing demo's auto-play passes record: false, so it never fills the workspace log.
      if (options.record !== false) setHistory(rows => [result, ...rows.filter(r => r.session_id !== result.session_id)].slice(0, 50))
    } catch (err) {
      if (controller.signal.aborted) return
      setError(classify(err)); setStatus('error')
    }
  }, [])

  const reset = useCallback(() => { pending.current?.abort(); setData(null); setError(null); setStatus('idle') }, [])
  const selectSession = useCallback(session => { pending.current?.abort(); setData(session); setError(null); setStatus('complete') }, [])
  const retry = useCallback(() => { if (lastInput.current) runAnalysis(lastInput.current.input, lastInput.current.options) }, [runAnalysis])
  const clearHistory = useCallback(() => setHistory([]), [])

  const value = useMemo(
    () => ({ status, data, error, startedAt, history, runAnalysis, reset, retry, selectSession, clearHistory }),
    [status, data, error, startedAt, history, runAnalysis, reset, retry, selectSession, clearHistory],
  )
  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAnalysis() {
  const context = useContext(AnalysisContext)
  if (!context) throw new Error('useAnalysis requires AnalysisProvider')
  return context
}
