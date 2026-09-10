export const SCENARIOS = [
  { id: 'hinglish_scam', name: 'The urgent wire transfer', short: 'Hinglish CEO scam', language: 'Hinglish', icon: 'transfer', scores: [.76, .88, .4], transcript: 'Turant 10 lakh transfer kar do. Confidential deal hai, kisi ko mat batana.', flags: ['Urgency', 'Secrecy', 'Authority impersonation'], jitter: .14, spectral: .52 },
  { id: 'hindi_kyc', name: 'The account verification trap', short: 'Hindi KYC fraud', language: 'Hindi', icon: 'lock', scores: [.72, .85, .5], transcript: 'आपका बैंक खाता ब्लॉक हो गया है। तुरंत वेरिफिकेशन के लिए ओटीपी बताएं, वरना खाता बंद रहेगा।', flags: ['Urgency', 'Credential harvesting'], jitter: .18, spectral: .46 },
  { id: 'cxo_safe', name: 'An ordinary morning briefing', short: 'Genuine Indian English', language: 'Indian English', icon: 'shield', scores: [.11, .05, .1], transcript: 'Good morning team. Let’s review the quarterly compliance and risk audit report as scheduled.', flags: [], jitter: 1.24, spectral: .12 },
  { id: 'synthetic_clone', name: 'A familiar voice. A false identity.', short: 'Synthetic voice clone', language: 'English', icon: 'wave', scores: [.92, .65, .65], transcript: 'I am authorizing this emergency wire transfer directly. Proceed immediately without the usual approval.', flags: ['Synthetic artifacts', 'Urgency', 'Authority impersonation'], jitter: .08, spectral: .64 },
]
export const percent = value => Number.isFinite(value) ? `${Math.round(value * 100)}%` : '—'
export function verdict(data) {
  if (!data || data.quality === 'insufficient' || data.state === 'insufficient') return { label: 'Insufficient evidence', tone: 'neutral' }
  if (data.state === 'high') return { label: 'High risk', tone: 'high' }
  if (data.state === 'review') return { label: 'Review needed', tone: 'caution' }
  if (data.state === 'low') return { label: 'Low risk', tone: 'safe' }
  return data.final_risk_score >= .7 ? { label: 'High risk', tone: 'high' } : data.final_risk_score >= .4 ? { label: 'Review needed', tone: 'caution' } : { label: 'Low risk', tone: 'safe' }
}
export function demoAnalysis(id) {
  const scenario = SCENARIOS.find(s => s.id === id)
  if (!scenario) throw new Error('Unknown demo scenario.')
  const [acoustic, linguistic, context] = scenario.scores
  const final = acoustic * .55 + linguistic * .25 + context * .2
  return {
    session_id: `demo_${crypto.randomUUID().slice(0, 8)}`, source: 'demo', name: scenario.short,
    timestamp: Date.now(), quality: 'ok', final_risk_score: final, acoustic_risk_score: acoustic,
    linguistic_risk_score: linguistic, context_risk: context, transcript: scenario.transcript,
    flags: scenario.flags, lang_detected: scenario.language, challenge_triggered: final >= .5,
    fusion_breakdown: { weights: { acoustic: .55, linguistic: .25, context: .2 }, raw_scores: { acoustic, linguistic, context }, contributions: { acoustic: acoustic * .55, linguistic: linguistic * .25, context: context * .2 }, calculated_raw: final },
    explainability: { jitter_pct: scenario.jitter, spectral_discontinuity: scenario.spectral, diagnostic_reasons: scenario.flags.length ? ['The sample combines acoustic anomalies with language that pressures the listener to act.', 'These values are prepared demo data, not measurements from an uploaded recording.'] : ['This sample illustrates low acoustic and linguistic risk.', 'Low risk is not proof of caller identity.'] },
  }
}
export function normalizeAnalysis(raw, name) {
  if (!raw || typeof raw !== 'object') throw new Error('The service returned an invalid analysis.')
  const final = raw.final_risk_score ?? raw.final_risk
  if (!Number.isFinite(final) || final < 0 || final > 1) throw new Error('The service did not return a valid risk score.')
  const score = value => Number.isFinite(value) && value >= 0 && value <= 1 ? value : null
  return { ...raw, final_risk_score: final, source: 'live', timestamp: raw.server_ts || Date.now(), name,
    session_id: raw.session_id || `local_${crypto.randomUUID().slice(0, 8)}`,
    acoustic_risk_score: score(raw.acoustic_risk_score ?? raw.spoof_score), linguistic_risk_score: score(raw.linguistic_risk_score ?? raw.linguistic_score),
    transcript: typeof raw.transcript === 'string' ? raw.transcript : '', flags: Array.isArray(raw.flags) ? raw.flags.filter(f => typeof f === 'string') : [],
  }
}
export const API_BASE = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/$/, '')
export async function request(path, options = {}, timeoutMs = 30000) {
  const signal = options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs)
  const response = await fetch(`${API_BASE}${path}`, { ...options, signal })
  if (!response.ok) throw new Error(`The analysis service returned ${response.status}. Please try again.`)
  return response.json()
}
