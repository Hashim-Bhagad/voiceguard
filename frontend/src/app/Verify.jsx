import { wakeBackend } from '@/lib/backend'
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Alert, Button, Chip, Spinner } from '@heroui/react'
import { Check, Mic, RefreshCw, ShieldAlert, ShieldCheck, ShieldQuestion, Square } from 'lucide-react'
import { useAnalysis } from '@/lib/AnalysisContext'
import { useRecorder } from '@/lib/useRecorder'
import { percent, request } from '@/lib/analysis'
import { ButtonLink, PageHeader } from './components/ui'
import AudioScope from './components/AudioScope'

const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
const STEPS = ['Generate a code', 'Caller repeats it', 'Compare', 'Decide']

function demoChallenge() {
  const tokens = Array.from(crypto.getRandomValues(new Uint8Array(4)), n => String(n % 10))
  return { display_code: tokens.join(' '), tokens, session_id: `demo_${crypto.randomUUID().slice(0, 8)}`, source: 'demo', expiresAt: Date.now() + 30000 }
}

function Stepper({ step }) {
  return (
    <ol className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Verification steps">
      {STEPS.map((label, i) => {
        const done = i < step, active = i === step
        return (
          <li key={label} aria-current={active ? 'step' : undefined} className="flex flex-col gap-2">
            <span className={`h-0.5 rounded-full transition-colors ${done || active ? 'bg-accent' : 'bg-default'}`} />
            <span className={`flex items-center gap-1.5 text-xs ${active ? 'text-foreground' : 'text-muted'}`}>
              {done && <Check aria-hidden className="size-3 text-success" />}{label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

const RESULT_VIEW = {
  pass: { Icon: ShieldCheck, color: 'success', text: 'text-success', label: 'Passed', title: 'The caller repeated the code.' },
  fail: { Icon: ShieldAlert, color: 'danger', text: 'text-danger', label: 'Failed', title: 'Verify another way before acting.' },
  uncertain: { Icon: ShieldQuestion, color: 'warning', text: 'text-warning', label: 'Inconclusive', title: 'No conclusion was reached.' },
}

export default function Verify() {
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
      setError(err.message === 'Failed to fetch' || err.name === 'TimeoutError'
        ? 'The verification service is unavailable. Retry a live challenge or try the demo.'
        : err.message)
      setPhase('ready')
    }
  }

  async function verify(blob) {
    if (!challenge || challenge.source !== 'live') return
    setPhase('verifying'); setError(null)
    const controller = new AbortController()
    operation.current = controller
    try {
      if (!blob.size) throw new Error('No audio was captured. Generate a fresh code and try again.')
      const form = new FormData()
      form.append('session_id', challenge.session_id)
      const extension = blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'
      form.append('file', blob, `challenge.${extension}`)
      const response = await request('/api/v1/challenge/verify-audio', { method: 'POST', body: form, signal: controller.signal })
      if (controller.signal.aborted) return
      if (!['pass', 'fail', 'uncertain'].includes(response.result)) throw new Error('No verification verdict was returned.')
      setResult({ ...response, source: 'live' }); setPhase('result')
    } catch (err) {
      if (controller.signal.aborted) return
      setResult({ result: 'uncertain', source: 'live', reason: err.name === 'TimeoutError' ? 'Verification timed out. No identity or liveness conclusion was made.' : 'Verification could not be completed. Generate a fresh code and try again.' })
      setPhase('result')
    }
  }

  function simulate(pass) {
    setResult({
      source: 'demo', result: pass ? 'pass' : 'fail', matched_count: pass ? 4 : 2, match_ratio: pass ? 1 : 0.5,
      spoken_digits: pass ? challenge.tokens : challenge.tokens.slice(0, 2), latency_ms: pass ? 840 : 3200, spoof_score: pass ? 0.12 : 0.81,
      reason: pass ? 'This prepared example shows all four digits matched with low acoustic risk. No speaker was recorded.' : 'This prepared example shows only two digits matched and elevated acoustic risk. No real caller was evaluated.',
    })
    setPhase('result')
  }

  const step = phase === 'result' ? 3 : phase === 'verifying' ? 2 : recorder.state === 'recording' ? 1 : challenge ? 1 : 0
  const view = result ? RESULT_VIEW[result.result] : null
  const expired = remaining === 0

  return (
    <div className="flex flex-col gap-12">
      <PageHeader title="Verify the caller" action={data && <ButtonLink to="/dashboard" variant="ghost" size="sm">Back to the analysis</ButtonLink>}>
        A clone can sound right but struggle with something it did not expect. Ask the caller to repeat a fresh four-digit code, and compare what comes back.
      </PageHeader>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
        <section className="flex flex-col gap-8 rounded-2xl border border-border bg-surface p-5 sm:p-8" aria-live="polite">
          <Stepper step={step} />
          <AnimatePresence mode="wait">
            <motion.div
              key={phase === 'creating' ? 'creating' : result ? 'result' : challenge ? `prompt-${challenge.session_id}` : 'ready'}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
              className="flex flex-col gap-6"
            >
              {phase === 'creating' ? (
                <div className="flex items-center gap-3 py-10 text-sm text-muted" role="status"><Spinner size="sm" />Generating a fresh code</div>
              ) : !challenge ? (
                <>
                  <div className="flex flex-col gap-3">
                    <h2 className="text-xl font-semibold tracking-[-0.015em]">Put the voice to the test.</h2>
                    <p className="max-w-xl text-[0.95rem] leading-relaxed text-muted">Generate a code, read it to the caller, and record their reply. Live codes expire after 30 seconds.</p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button variant="primary" onHoverStart={wakeBackend} onFocus={wakeBackend} onPress={() => create('live')}>Generate a live code</Button>
                    <Button variant="secondary" onPress={() => create('demo')}>Try the demo</Button>
                  </div>
                </>
              ) : result ? (
                <>
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Chip color={view.color} variant="soft" size="sm"><view.Icon aria-hidden className="size-3.5" /><Chip.Label>{result.source === 'demo' ? `Simulated · ${view.label}` : view.label}</Chip.Label></Chip>
                    </div>
                    <h2 className="text-xl font-semibold tracking-[-0.015em]">{view.title}</h2>
                    <p className="max-w-xl text-[0.95rem] leading-relaxed text-muted">{result.reason}</p>
                  </div>
                  <dl className="grid grid-cols-1 gap-6 sm:grid-cols-3">
                    <div className="flex flex-col gap-1"><dt className="text-xs text-muted">Digits matched</dt><dd className="font-pixel text-4xl tabular">{result.matched_count ?? '?'}<span className="text-xl text-muted"> / 4</span></dd></div>
                    <div className="flex flex-col gap-1"><dt className="text-xs text-muted">Voice spoof score</dt><dd className={`font-pixel text-4xl tabular ${view.text}`}>{percent(result.spoof_score)}</dd></div>
                    <div className="flex flex-col gap-1"><dt className="text-xs text-muted">{result.source === 'demo' ? 'Example elapsed' : 'Elapsed'}</dt><dd className="font-pixel text-4xl tabular">{Number.isFinite(result.latency_ms) ? result.latency_ms.toLocaleString() : '?'}<span className="text-xl text-muted"> ms</span></dd></div>
                  </dl>
                  {Array.isArray(result.spoken_digits) && <p className="font-mono text-sm text-muted">Heard: {result.spoken_digits.join(' ') || 'nothing'}</p>}
                  <p className="text-xs text-muted">Elapsed time includes the whole exchange. It is not a reflex measurement and not proof of identity.</p>
                  <div><Button variant="secondary" onPress={() => create(result.source)}><RefreshCw aria-hidden className="size-4" />Generate another code</Button></div>
                </>
              ) : (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="label-mono">Ask the caller to repeat</span>
                    <span className={`font-mono text-sm tabular ${expired || remaining <= 10 ? 'text-warning' : 'text-muted'}`} aria-live="off">
                      {expired ? 'Code expired' : `${remaining}s left`}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-3" role="group" aria-label={`Code: ${challenge.tokens.join(' ')}`}>
                    {challenge.tokens.map((digit, i) => (
                      <motion.span
                        key={`${challenge.session_id}-${i}`}
                        initial={{ opacity: 0, y: 14, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                        transition={{ delay: i * 0.08, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                        className={`grid h-24 w-[4.5rem] place-items-center rounded-xl bg-ink-0 font-pixel text-6xl tabular sm:h-28 sm:w-20 sm:text-7xl ${expired ? 'text-muted' : 'text-accent'}`}
                      >{digit}</motion.span>
                    ))}
                  </div>
                  <p className="text-lg text-foreground">“{challenge.tokens.map(n => WORDS[Number(n)]).join(' ')}”</p>

                  {challenge.source === 'demo' ? (
                    <div className="flex flex-col gap-3">
                      <p className="text-sm text-muted">Demo mode. Pick an outcome to see how a result reads.</p>
                      <div className="flex flex-wrap gap-3">
                        <Button variant="secondary" isDisabled={expired} onPress={() => simulate(true)}><Check aria-hidden className="size-4" />Simulate a pass</Button>
                        <Button variant="danger-soft" isDisabled={expired} onPress={() => simulate(false)}><ShieldAlert aria-hidden className="size-4" />Simulate a fail</Button>
                      </div>
                    </div>
                  ) : phase === 'verifying' ? (
                    <div className="flex items-center gap-3 text-sm text-muted" role="status"><Spinner size="sm" />Comparing the digits and the voice</div>
                  ) : recorder.state === 'recording' ? (
                    <div className="flex flex-col gap-4">
                      <AudioScope stream={recorder.stream} label="Recording the reply" />
                      <div><Button variant="primary" onPress={recorder.stop}><Square aria-hidden className="size-3.5 fill-current" />Stop and verify · {recorder.seconds}s</Button></div>
                    </div>
                  ) : (
                    <div><Button variant="primary" isDisabled={expired || recorder.state === 'requesting'} onHoverStart={wakeBackend} onFocus={wakeBackend} onPress={recorder.start}><Mic aria-hidden className="size-4" />{recorder.state === 'requesting' ? 'Allow microphone access' : 'Record the reply'}</Button></div>
                  )}
                  {!busy && (
                    <button type="button" onClick={() => create(challenge.source)} className="inline-flex w-fit items-center gap-1.5 text-sm text-muted underline-offset-4 hover:text-foreground hover:underline">
                      <RefreshCw aria-hidden className="size-3.5" />Generate a fresh code
                    </button>
                  )}
                </>
              )}
            </motion.div>
          </AnimatePresence>
          {(error || recorder.error) && (
            <Alert status="danger" role="alert">
              <Alert.Indicator />
              <Alert.Content><Alert.Title>Something went wrong</Alert.Title><Alert.Description>{error || recorder.error}</Alert.Description></Alert.Content>
            </Alert>
          )}
        </section>

        <aside className="flex flex-col gap-8">
          <div className="flex flex-col gap-2">
            <span className="label-mono">Context</span>
            {data ? (
              <>
                <p className="text-sm font-medium text-foreground">{data.name}</p>
                <p className="text-sm text-muted">{data.source === 'demo' ? 'Prepared demo' : 'Live analysis'} · {percent(data.final_risk_score)} combined risk</p>
              </>
            ) : (
              <p className="text-sm leading-relaxed text-muted">No analysis is open. A liveness check works on its own, or run an analysis first so the result travels with it.</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <span className="label-mono">Read this first</span>
            <p className="text-sm leading-relaxed text-muted">A failed or expired code means verify another way. On its own it does not prove the caller is a clone, and a pass does not prove who they are.</p>
          </div>
        </aside>
      </div>
    </div>
  )
}
