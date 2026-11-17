import { MARKER_RELIABILITY, verdict } from './analysis'

/*
  Turns one /verify/file response (live or prepared) into the explanation the result
  screen shows. Every sentence is built from a field the service returned; nothing
  is claimed that the response does not contain.

  The service's own audit (backend/app/services/explainability.py) is the authority
  on what counts as evidence: only the acoustic model is validated (AUC 0.82). Pitch
  jitter, spectral discontinuity and prosody are reported but explicitly unusable, so
  they are shown as "measured, not used", never as reasons.
*/

const pct = v => `${Math.round(v * 100)}%`
const fin = v => Number.isFinite(v)

export const ACTIONS = {
  hold: { title: 'Hold the request', text: 'Do not send money or share codes until you have verified the caller another way.' },
  verify: { title: 'Verify before acting', text: 'Call back on a number you already trust, or run a liveness check.' },
  continue: { title: 'No action needed', text: 'Nothing here calls for a hold. Low risk is still not proof of who is calling.' },
}

export function explain(data) {
  const v = verdict(data)
  const ex = data.explainability || {}
  const fusion = data.fusion_breakdown || {}
  const weights = fusion.weights || { acoustic: 0.55, linguistic: 0.25, context: 0.2 }
  const raw = fusion.raw_scores || { acoustic: data.acoustic_risk_score, linguistic: data.linguistic_risk_score, context: data.context_risk }
  const c = fusion.contributions || {}
  const voice = raw.acoustic
  const insufficient = data.quality === 'insufficient' || data.state === 'insufficient'

  // Flagged words: prefer the service's categorised list, fall back to bare flags.
  const hits = Array.isArray(ex.threat_categories) && ex.threat_categories.length
    ? ex.threat_categories.map(h => ({ keyword: h.keyword, category: h.category }))
    : (Array.isArray(data.flags) ? data.flags : []).map(k => ({ keyword: k, category: null }))

  // What each signal added to the final score, in points.
  const part = (key, fallback) => (fin(c[key]) ? c[key] : fallback)
  const contributions = [
    {
      key: 'acoustic', label: 'Voice model', what: 'How synthetic the voice sounds',
      score: raw.acoustic, weight: weights.acoustic, points: part('acoustic', fin(raw.acoustic) ? raw.acoustic * weights.acoustic : null),
      basis: 'Validated · AUC 0.82', kind: 'evidence',
    },
    {
      key: 'linguistic', label: 'Words', what: hits.length ? `${hits.length} pressure ${hits.length === 1 ? 'cue' : 'cues'} matched` : 'No pressure cues matched',
      score: raw.linguistic, weight: weights.linguistic, points: part('linguistic', fin(raw.linguistic) ? raw.linguistic * weights.linguistic : null),
      basis: 'Keyword match', kind: 'evidence',
    },
    {
      key: 'context', label: 'Policy', what: 'Fixed by the policy profile, not measured',
      score: raw.context, weight: weights.context, points: part('context', fin(raw.context) ? raw.context * weights.context : null),
      basis: 'Setting', kind: 'setting',
    },
  ]
  if (fin(c.prosody_penalty) && c.prosody_penalty > 0) {
    contributions.push({ key: 'prosody', label: 'Flat prosody', what: 'Small fixed penalty', score: null, weight: null, points: c.prosody_penalty, basis: 'Unvalidated', kind: 'setting' })
  }
  const sum = contributions.reduce((n, x) => n + (fin(x.points) ? x.points : 0), 0)
  const smoothing = fin(data.final_risk_score) ? data.final_risk_score - sum : 0

  // The headline reason, sentence by sentence, from returned fields only.
  let summary
  if (insufficient) summary = 'Not enough clear speech to judge. Use at least a few seconds of one voice.'
  else {
    const s = []
    if (fin(voice)) {
      s.push(voice >= 0.55
        ? `The voice model rates this voice ${pct(voice)} likely synthetic.`
        : voice >= 0.35
          ? `The voice model found some synthetic-like patterns (${pct(voice)}).`
          : `The voice model rates this voice ${pct(voice)} likely synthetic, which is low.`)
    }
    if (hits.length) {
      const quoted = hits.slice(0, 2).map(h => `“${h.keyword}”`).join(' and ')
      s.push(`The words include ${hits.length === 1 ? 'a pressure cue' : `${hits.length} pressure cues`}, such as ${quoted}.`)
    } else if (data.transcript) {
      s.push('No pressure or secrecy cues in the words.')
    }
    summary = s.join(' ')
  }

  const rel = { ...MARKER_RELIABILITY, ...(ex.marker_reliability || {}) }
  const markers = [
    {
      key: 'jitter', label: 'Pitch micro-jitter',
      value: fin(ex.jitter_pct) ? `${ex.jitter_pct.toFixed(2)}%` : null,
      note: ex.jitter_verdict === 'unreliable_estimator_saturated'
        ? 'The estimator hit its ceiling on this clip, so the number means nothing here.'
        : `Not used. Separates real and cloned clips no better than chance (AUC ${rel.jitter_pct.auc}).`,
    },
    {
      key: 'spectral', label: 'Spectral discontinuity, 3 to 4.5 kHz',
      value: fin(ex.spectral_discontinuity) ? ex.spectral_discontinuity.toFixed(2) : null,
      note: `Not used. Weak (AUC ${rel.spectral_discontinuity.auc}): fires on 22% of real and 30% of cloned clips.`,
    },
    {
      key: 'prosody', label: 'Prosody', value: ex.prosody_flatness || data.prosody_flag || null,
      note: `Not used. Flat prosody shows up as often in real speech (AUC ${rel.prosody_flatness.auc}).`,
    },
  ]

  const action = ACTIONS[data.action] || ACTIONS[v.tone === 'high' ? 'hold' : v.tone === 'caution' ? 'verify' : 'continue']

  return {
    tone: v.tone, label: v.label, summary, action, hits, contributions, sum, smoothing, markers,
    primary: ex.primary_evidence || (fin(voice) && voice >= 0.35 ? 'acoustic_model' : 'none'),
    measuredOn: ex.measured_on || null,
    modelVer: data.model_ver || null,
    // Only a real detection is called one; an echoed hint is labelled as the hint.
    language: !data.lang_detected || data.lang_detected === 'auto' ? null
      : data.lang_source === 'hint' ? `${data.lang_detected} (your hint)`
      : data.lang_source === 'whisper' ? `${data.lang_detected[0].toUpperCase()}${data.lang_detected.slice(1)}, detected`
      : data.lang_source === 'none' ? null
      : data.lang_detected,
    segments: Array.isArray(data.segments) ? data.segments.filter(s => Number.isFinite(s?.spoof_score) && Number.isFinite(s?.start_s)) : [],
    notes: Array.isArray(ex.diagnostic_reasons) ? ex.diagnostic_reasons : [],
  }
}

// Splits a transcript into plain and flagged runs, so cues can be marked in place.
export function markTranscript(text, hits) {
  if (!text || !hits.length) return [{ text }]
  const lower = text.toLowerCase()
  const spans = []
  for (const h of hits) {
    const k = h.keyword.toLowerCase()
    let from = 0, at
    while (k && (at = lower.indexOf(k, from)) !== -1) {
      if (!spans.some(s => at < s.end && at + k.length > s.start)) spans.push({ start: at, end: at + k.length, hit: h })
      from = at + k.length
    }
  }
  spans.sort((a, b) => a.start - b.start)
  const out = []
  let i = 0
  for (const s of spans) {
    if (s.start > i) out.push({ text: text.slice(i, s.start) })
    out.push({ text: text.slice(s.start, s.end), hit: s.hit })
    i = s.end
  }
  if (i < text.length) out.push({ text: text.slice(i) })
  return out
}
