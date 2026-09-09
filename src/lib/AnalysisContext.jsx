import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const MOCK_ANALYSIS = {
  acoustic_risk_score: 0.62,
  linguistic_risk_score: 0.48,
  final_risk_score: 0.57,
  transcript:
    "Hi, this is Alex calling from your bank's security department. We've detected unusual activity on your account and need to verify your identity right away. Can you confirm your card number and the security code on the back?",
  flags: [
    'urgency_language',
    'impersonation_bank_official',
    'request_for_sensitive_info',
    'synthetic_voice_artifacts',
  ],
  challenge_triggered: true,
}

const AnalysisContext = createContext(null)

export function AnalysisProvider({ children }) {
  const [status, setStatus] = useState('idle')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const runAnalysis = useCallback(async (audioInput) => {
    setStatus('analyzing')
    setError(null)
    try {
      await new Promise((resolve) => setTimeout(resolve, 1600))
      setData(MOCK_ANALYSIS)
      setStatus('complete')
    } catch (err) {
      setError(err)
      setStatus('error')
    }
  }, [])

  const reset = useCallback(() => {
    setStatus('idle')
    setData(null)
    setError(null)
  }, [])

  const value = useMemo(
    () => ({ status, data, error, runAnalysis, reset }),
    [status, data, error, runAnalysis, reset]
  )

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}

export function useAnalysis() {
  const ctx = useContext(AnalysisContext)
  if (!ctx) throw new Error('useAnalysis() must be called within an <AnalysisProvider>')
  return ctx
}