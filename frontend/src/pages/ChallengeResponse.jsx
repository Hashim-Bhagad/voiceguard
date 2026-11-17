import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { useAnalysis } from '../lib/AnalysisContext'
import { useRecorder } from '../lib/useRecorder'
import { request, percent } from '../lib/analysis'
import { Icon, PageHeading, Panel } from '../components/ui'
import { AudioScope } from '../components/SignalGraphics'
const words = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
function demoChallenge() {
  const tokens = Array.from(crypto.getRandomValues(new Uint8Array(4)), n => String(n % 10))
  return { display_code: tokens.join(' '), tokens, session_id: `demo_${crypto.randomUUID().slice(0, 8)}`, source: 'demo', expiresAt: Date.now() + 30000 }
}
export default function ChallengeResponse() {
  const { data } = useAnalysis()
  const [challenge, setChallenge] = useState(null)
  const [phase, setPhase] = useState('ready')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [remaining, setRemaining] = useState(30)
  const operation = useRef(null)
  const recorder = useRecorder(verify)
  const busy = phase === 'creating' || phase === 'verifying' || recorder.state !== 'idle'
  useEffect(() => () => operation.current?.abort(), [])
  useEffect(() => {
    if (!challenge) return
    const timer = setInterval(() => setRemaining(Math.max(0, Math.ceil((challenge.expiresAt - Date.now()) / 1000))), 250)
    return () => clearInterval(timer)
  }, [challenge])
  async function create(mode) {
    operation.current?.abort()
    const controller = new AbortController()
    operation.current = controller
    setPhase('creating'); setResult(null); setError(null); setChallenge(null)
    try {
      let next
      if (mode === 'demo') next = demoChallenge()
      else {
        const sid = data?.source === 'live' ? `?session_id=${encodeURIComponent(data.session_id)}` : ''
        const response = await request(`/api/v1/challenge/create${sid}`, { method: 'POST', signal: controller.signal }, 45000)
        const tokens = response.tokens || String(response.display_code || '').split(/\s+/)
        if (!response.session_id || tokens.length !== 4 || tokens.some(n => !/^\d$/.test(n))) throw new Error('The service returned an invalid challenge. Please retry.')
        next = { ...response, tokens, source: 'live', expiresAt: Date.now() + (response.expires_in_s || 30) * 1000 }
      }
      if (controller.signal.aborted) return
      setChallenge(next); setRemaining(Math.ceil((next.expiresAt - Date.now()) / 1000)); setPhase('prompt')
    } catch (err) {
      if (controller.signal.aborted) return
      setError(err.message === 'Failed to fetch' || err.name === 'TimeoutError' ? 'The verification service is unavailable. Retry a live challenge or choose the labeled demo.' : err.message)
      setPhase('ready')
    }
  }
  async function verify(blob) {
    if (!challenge || challenge.source !== 'live') return
    setPhase('verifying'); setError(null)
    const controller = new AbortController()
    operation.current = controller
    try {
      if (!blob.size) throw new Error('No audio was captured. Generate a fresh challenge and try again.')
      const form = new FormData()
      form.append('session_id', challenge.session_id)
      const extension = blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'
      form.append('file', blob, `challenge.${extension}`)
      const response = await request('/api/v1/challenge/verify-audio', { method: 'POST', body: form, signal: controller.signal })
      if (controller.signal.aborted) return
      if (!['pass', 'fail', 'uncertain'].includes(response.result)) throw new Error('No verification verdict was returned. Generate a fresh challenge and retry.')
      setResult({ ...response, source: 'live' }); setPhase('result')
    } catch (err) {
      if (controller.signal.aborted) return
      setResult({ result: 'uncertain', source: 'live', reason: err.name === 'TimeoutError' ? 'Verification timed out. No identity or liveness conclusion was made.' : 'Verification could not be completed. Generate a fresh challenge and try again.' }); setPhase('result')
    }
  }
  function simulate(pass) {
    setResult({ source: 'demo', result: pass ? 'pass' : 'fail', matched_count: pass ? 4 : 2, match_ratio: pass ? 1 : .5, spoken_digits: pass ? challenge.tokens : challenge.tokens.slice(0, 2), latency_ms: pass ? 840 : 3200, spoof_score: pass ? .12 : .81, reason: pass ? 'This prepared example shows matching digits with low acoustic risk. No speaker was recorded or verified.' : 'This prepared example shows incomplete token matching and elevated acoustic risk. No real caller was evaluated.' }); setPhase('result')
  }
  const step = phase === 'result' ? 3 : phase === 'verifying' || recorder.state === 'recording' ? 2 : challenge ? 1 : 0
  const tone = result?.result === 'pass' ? 'safe' : result?.result === 'fail' ? 'high' : 'caution'
  return <><PageHeading eyebrow="ACTIVE VERIFICATION" title="A fresh prompt. A closer check." action={<Link className="button ghost compact" to="/dashboard">Back to analysis <Icon name="arrow" size={16} /></Link>}>Compare what the caller says with a new challenge and inspect the acoustic evidence.</PageHeading><div className="verification-layout"><Panel className="challenge-stage"><div className="challenge-stage-top"><span className="eyebrow">CALLER LIVENESS</span><span className={`badge ${challenge?.source === 'demo' ? 'demo' : 'neutral'}`}>{challenge?.source === 'demo' ? 'DEMO MODE' : 'LIVE VERIFICATION'}</span></div><div className={`verification-orbit ${recorder.state === 'recording' ? 'listening' : ''}`} aria-hidden="true"><span className="orbit-track" /><span className="orbit-track inner" /><span className="verification-shield"><Icon name={result ? result.result === 'pass' ? 'check' : 'alert' : 'shield'} size={38} /></span></div><AnimatePresence mode="wait"><motion.div key={phase === 'creating' ? 'creating' : result ? 'result' : challenge ? 'prompt' : 'ready'} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: .22 }} className="challenge-content">{phase === 'creating' ? <div className="challenge-wait" role="status"><span className="spinner" />Generating a fresh challenge…</div> : !challenge ? <><h2>Put the voice to the test.</h2><p>Generate a four-digit prompt, then ask the caller to repeat it. Live challenges expire after 30 seconds.</p><div className="challenge-primary-actions"><button className="button primary" onClick={() => create('live')}>Generate live challenge <Icon name="arrow" size={17} /></button><button className="button ghost" onClick={() => create('demo')}>Explore demo</button></div></> : result ? <><span className={`badge ${tone}`}>{result.source === 'demo' ? 'SIMULATED ' : ''}{result.result === 'uncertain' ? 'INCONCLUSIVE' : result.result.toUpperCase()}</span><h2>{result.result === 'pass' ? 'Challenge passed.' : result.result === 'fail' ? 'Further verification needed.' : 'No conclusion was reached.'}</h2><p>{result.reason}</p><div className="verification-metrics"><div><span>Matched tokens</span><strong>{result.matched_count ?? '—'}<small> / 4</small></strong></div><div><span>Acoustic risk</span><strong>{percent(result.spoof_score)}</strong></div><div><span>{result.source === 'demo' ? 'Example elapsed time' : 'Challenge elapsed time'}</span><strong>{Number.isFinite(result.latency_ms) ? result.latency_ms.toLocaleString() : '—'}<small> ms</small></strong></div></div>{Array.isArray(result.spoken_digits) && <p className="spoken-digits">Reported digits: {result.spoken_digits.join(' · ') || 'None'}</p>}<p className="verification-caveat">Elapsed time includes the challenge interaction; it is not a measurement of human reflex or proof of identity.</p><button className="button primary" onClick={() => create(result.source)}>Generate another challenge <Icon name="arrow" size={16} /></button></> : <><div className="prompt-meta"><span>ASK THE CALLER TO REPEAT</span><span className={remaining === 0 ? 'tone-high' : ''}>{remaining > 0 ? `${remaining}s remaining` : 'Challenge expired'}</span></div><div className="challenge-digits">{challenge.tokens.map((digit, i) => <motion.span key={`${challenge.session_id}-${i}`} initial={{ opacity: 0, rotateX: -60, y: 10 }} animate={{ opacity: 1, rotateX: 0, y: 0 }} transition={{ delay: i * .07 }}>{digit}</motion.span>)}</div><p className="spoken-prompt">“{challenge.tokens.map(n => words[Number(n)]).join(' ')}”</p>{challenge.source === 'demo' ? <div className="challenge-demo"><p>This is a simulation. Choose an example outcome.</p><div className="challenge-primary-actions"><button disabled={remaining === 0} className="button primary" onClick={() => simulate(true)}><Icon name="check" size={17} />Simulate pass</button><button disabled={remaining === 0} className="button danger" onClick={() => simulate(false)}><Icon name="alert" size={17} />Simulate fail</button></div></div> : phase === 'verifying' ? <div className="challenge-wait" role="status"><span className="spinner" />Comparing spoken tokens and acoustic evidence…</div> : recorder.state === 'recording' ? <><AudioScope stream={recorder.stream} active /><button className="button danger" onClick={recorder.stop}><span className="record-dot" />Stop & verify · {recorder.seconds}s</button></> : <button disabled={remaining === 0 || recorder.state === 'requesting'} className="button primary" onClick={recorder.start}><Icon name="mic" size={18} />{recorder.state === 'requesting' ? 'Allow microphone access…' : 'Record caller response'}</button>}{!busy && <button className="text-button" onClick={() => create(challenge.source)}>Generate a fresh code <Icon name="transfer" size={14} /></button>}</>}</motion.div></AnimatePresence>{(error || recorder.error) && <div role="alert" className="notice error-notice"><Icon name="alert" /><p>{error || recorder.error}</p></div>}</Panel><div className="verification-aside"><Panel title="Verification journey"><ol className="verification-timeline">{[['Generate', 'A new code for this conversation.'], ['Speak', 'Repeat each digit clearly.'], ['Compare', 'Check tokens and acoustic evidence.'], ['Review', 'Use the result with your other checks.']].map(([title, text], i) => <li key={title} className={i <= step ? 'reached' : ''}><span>{i < step ? <Icon name="check" size={13} /> : `0${i + 1}`}</span><div><strong>{title}</strong><p>{text}</p></div></li>)}</ol></Panel><Panel title="Keep the context"><div className="context-call"><Icon name="wave" /><strong>{data?.name || 'Standalone verification'}</strong></div><p className="aside-copy">{data ? `${data.source === 'demo' ? 'Demo' : 'Analysis'} session · ${percent(data.final_risk_score)} risk` : 'You can run a challenge independently or start with an audio analysis.'}</p><div className="aside-rule" /><p className="aside-copy">A failed or expired challenge needs further review. It does not, on its own, establish that the caller is a clone.</p></Panel></div></div></>
}
