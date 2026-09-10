import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { demoAnalysis, normalizeAnalysis, request } from './analysis'
const AnalysisContext = createContext(null)
export function AnalysisProvider({ children }) {
  const [status, setStatus] = useState('idle')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const pending = useRef(null)
  const lastInput = useRef(null)
  useEffect(() => () => { pending.current?.abort(); lastInput.current = null }, [])
  const runAnalysis = useCallback(async (input, options = {}) => {
    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller
    lastInput.current = { input, options }
    setStatus('analyzing'); setError(null); setData(null)
    try {
      let result
      if (typeof input === 'string') result = demoAnalysis(input)
      else {
        if (!(input instanceof Blob) || input.size === 0) throw new Error('Choose a non-empty audio recording.')
        if (input.size > 25 * 1024 * 1024) throw new Error('Please use a recording smaller than 25 MB.')
        const form = new FormData()
        const extension = input.type.includes('mp4') ? 'm4a' : input.type.includes('ogg') ? 'ogg' : input.type.includes('webm') ? 'webm' : 'wav'
        form.append('file', input, input.name || `recording.${extension}`)
        form.append('policy_profile', options.policy || 'standard')
        form.append('lang_hint', options.lang === 'auto-hinglish' ? 'auto' : options.lang || 'auto')
        result = normalizeAnalysis(await request('/api/v1/verify/file', { method: 'POST', body: form, signal: controller.signal }), input.name || 'Microphone recording')
      }
      if (controller.signal.aborted) return
      setData(result); setStatus('complete')
      setHistory(rows => [result, ...rows].slice(0, 50))
      lastInput.current = null
    } catch (err) {
      if (controller.signal.aborted) return
      setError(err.name === 'TimeoutError' ? 'The service took too long. Retry your recording or explore a labeled demo below.' : err.message === 'Failed to fetch' ? 'The analysis service is unavailable. Retry or choose a demo scenario below.' : err.message)
      setStatus('error')
    }
  }, [])
  const reset = useCallback(() => { pending.current?.abort(); lastInput.current = null; setData(null); setError(null); setStatus('idle') }, [])
  const selectSession = useCallback(session => { pending.current?.abort(); lastInput.current = null; setData(session); setError(null); setStatus('complete') }, [])
  const retry = useCallback(() => { if (lastInput.current) runAnalysis(lastInput.current.input, lastInput.current.options) }, [runAnalysis])
  const value = useMemo(() => ({ status, data, error, history, runAnalysis, reset, retry, selectSession }), [status, data, error, history, runAnalysis, reset, retry, selectSession])
  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}
// eslint-disable-next-line react-refresh/only-export-components
export function useAnalysis() {
  const context = useContext(AnalysisContext)
  if (!context) throw new Error('useAnalysis requires AnalysisProvider')
  return context
}
