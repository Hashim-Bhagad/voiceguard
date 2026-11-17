import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion, useAnimate, useReducedMotion } from 'motion/react'
import NumberFlow from '@number-flow/react'
import { ArrowRight, Check, Pause, ShieldAlert, ShieldCheck, TriangleAlert } from 'lucide-react'
import { SCENARIOS, verdict } from '../lib/analysis'
import { useAnalysis } from '../lib/AnalysisContext'
import { MaskLines, BlurIn } from './Reveal'
import LineScope from './LineScope'

const EASE = [0.16, 1, 0.3, 1]
const STAGES = ['Transcribing the call', 'Scanning the voice with XLS-R', 'Reading the language', 'Fusing the signals']
const TONE = {
  high: { text: 'text-danger', ring: 'border-danger/40', Icon: ShieldAlert },
  caution: { text: 'text-warning', ring: 'border-warning/40', Icon: TriangleAlert },
  safe: { text: 'text-success', ring: 'border-success/40', Icon: ShieldCheck },
  neutral: { text: 'text-muted', ring: 'border-border', Icon: ShieldCheck },
}

// Remounted for every run (keyed by the parent), so the steps always start from the top.
function Stages() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setStep(s => Math.min(STAGES.length - 1, s + 1)), 340)
    return () => clearInterval(id)
  }, [])
  return (
    <ol className="flex flex-col gap-3" aria-label="Analysis steps">
      {STAGES.map((label, i) => {
        const state = i < step ? 'done' : i === step ? 'now' : 'next'
        return (
          <li key={label} aria-current={state === 'now' ? 'step' : undefined} className="flex items-center gap-3 text-sm">
            <span className={`grid size-5 place-items-center rounded-full border ${state === 'next' ? 'border-border' : 'border-accent'} ${state === 'done' ? 'bg-accent text-accent-foreground' : ''}`}>
              {state === 'done' ? <Check className="size-3" strokeWidth={3} /> : state === 'now' ? <span className="size-1.5 animate-pulse rounded-full bg-accent" /> : null}
            </span>
            <span className={state === 'next' ? 'text-muted' : 'text-foreground'}>{label}<span className="sr-only">{state === 'done' ? ', done' : state === 'now' ? ', in progress' : ''}</span></span>
          </li>
        )
      })}
    </ol>
  )
}

function Verdict({ data }) {
  const navigate = useNavigate()
  const { selectSession } = useAnalysis()
  const v = verdict(data)
  const tone = TONE[v.tone] || TONE.neutral
  const [shown, setShown] = useState(0)
  useEffect(() => { const id = requestAnimationFrame(() => setShown(data.final_risk_score)); return () => cancelAnimationFrame(id) }, [data])
  const open = path => { selectSession(data); navigate(path) }
  return (
    <motion.div
      className="flex flex-col gap-6"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6, ease: EASE, delay: 0.25 }}
      aria-live="polite"
    >
      <div>
        <p className={`inline-flex items-center gap-2 text-sm font-semibold ${tone.text}`}>
          <tone.Icon className="size-4" aria-hidden="true" />
          {v.label}
          <span className="font-normal text-muted">· combined risk</span>
        </p>
        <p className={`mt-3 font-pixel text-[clamp(3.5rem,8vw,5.75rem)] leading-none ${tone.text}`}>
          <NumberFlow value={shown} format={{ style: 'percent', maximumFractionDigits: 0 }} transformTiming={{ duration: 1100, easing: 'cubic-bezier(.16,1,.3,1)' }} />
        </p>
      </div>
      <blockquote className="border-l-2 border-border pl-4 text-[0.95rem] leading-relaxed text-foreground">{data.transcript}</blockquote>
      {data.flags.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Flags">
          {data.flags.map(f => (
            <li key={f} className="rounded-md border border-border px-2.5 py-1 font-mono text-xs text-muted">{f}</li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 pt-2">
        <button type="button" onClick={() => open('/dashboard')} className="group inline-flex items-center gap-2 text-sm font-medium text-foreground underline decoration-border underline-offset-[6px] hover:text-accent hover:decoration-accent">
          Open the full breakdown <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
        </button>
        {data.challenge_triggered && (
          <button type="button" onClick={() => open('/dashboard/challenge')} className="text-sm text-muted hover:text-foreground">
            Verify the caller
          </button>
        )}
      </div>
    </motion.div>
  )
}

// Three tiny pixel columns: still until the card is hovered, playing while it runs.
function Eq({ live }) {
  return (
    <span className={`eq mt-1 ${live ? 'is-live' : ''}`} aria-hidden="true">
      <span /><span /><span />
    </span>
  )
}

const HEADER = {
  idle: () => ({ dot: 'bg-grey-700', text: 'Line open · nobody talking' }),
  preview: s => ({ dot: 'bg-accent animate-pulse', text: `Incoming · ${s.language}` }),
  running: s => ({ dot: 'bg-amber-hot animate-pulse', text: `Listening · ${s.language}` }),
}

export default function DemoSection() {
  const reduce = useReducedMotion()
  const { runAnalysis, status, data } = useAnalysis()
  const [picked, setPicked] = useState(null)
  const [hovered, setHovered] = useState(null)
  const section = useRef(null)
  const running = status === 'analyzing' && picked !== null
  const result = data?.source === 'demo' && picked !== null ? data : null

  const pick = (id, options) => { setPicked(id); runAnalysis(id, options) }
  const pickRef = useRef(pick)
  const cardRefs = useRef([])
  useEffect(() => { pickRef.current = pick })

  // Auto-play: while the section is on screen and nobody has touched it, the calls
  // play themselves, each put on the line, run, and held on its verdict. Any hover,
  // focus, click or key hands control over for good. Auto runs aren't logged.
  const [auto, setAuto] = useState(!reduce)
  const [autoIndex, setAutoIndex] = useState(0)
  const [inView, setInView] = useState(false)
  const takeOver = () => { if (auto) setAuto(false) }
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), { threshold: 0.45 })
    if (section.current) io.observe(section.current)
    return () => io.disconnect()
  }, [])
  useEffect(() => {
    if (!auto || !inView) return
    const timers = []
    const play = i => {
      const s = SCENARIOS[i % SCENARIOS.length]
      setAutoIndex(i % SCENARIOS.length)
      setHovered(s.id)
      timers.push(setTimeout(() => { setHovered(null); pickRef.current(s.id, { record: false }) }, 1700))
      timers.push(setTimeout(() => play(i + 1), 1700 + 1400 + 3800))
    }
    timers.push(setTimeout(() => play(autoIndex), 500))
    return () => timers.forEach(clearTimeout)
    // autoIndex is read once to resume where the loop left off.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, inView])

  // The verdict lands with a small knock on the panel, without remounting the scope.
  const [panel, animatePanel] = useAnimate()
  const resultId = result?.session_id
  useEffect(() => {
    if (!resultId || reduce || !panel.current) return
    animatePanel(panel.current, { scale: [0.985, 1] }, { type: 'spring', stiffness: 380, damping: 18 })
  }, [resultId, reduce, animatePanel, panel])

  // Keys 1 to 4 pick a call while the section is on screen.
  useEffect(() => {
    let inView = false
    const io = new IntersectionObserver(([e]) => { inView = e.isIntersecting }, { threshold: 0.3 })
    if (section.current) io.observe(section.current)
    const onKey = e => {
      if (!inView || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.target instanceof HTMLElement && e.target.closest('input, textarea, select, [contenteditable]')) return
      const n = Number(e.key)
      if (n >= 1 && n <= SCENARIOS.length) {
        setAuto(false)
        // Focus follows the key, so the ring and the running card agree.
        cardRefs.current[n - 1]?.focus({ preventScroll: true })
        pickRef.current(SCENARIOS[n - 1].id)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => { io.disconnect(); window.removeEventListener('keydown', onKey) }
  }, [])

  const focusId = running || result ? picked : hovered
  const focus = SCENARIOS.find(s => s.id === focusId) || null
  const mode = running ? 'running' : result ? 'result' : focus ? 'preview' : 'idle'
  const v = result ? verdict(result) : null
  const tone = v ? TONE[v.tone] || TONE.neutral : null
  const head = mode === 'result'
    ? { dot: '', text: `${v.label} · ${focus?.language ?? ''}` }
    : HEADER[mode](focus)

  return (
    <section ref={section} id="demo" className="relative px-6 py-[clamp(6rem,16vh,10rem)] sm:px-8" aria-labelledby="demo-title">
      <div className="mx-auto grid max-w-[1240px] gap-16 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-20">
        <div className="flex flex-col gap-10">
          <div>
            <p className="label-mono text-accent">Live demo</p>
            <MaskLines as="h2" className="mt-4 text-[clamp(2.25rem,4.6vw,3.75rem)] font-display font-normal leading-[1] tracking-[0.005em]">
              <span id="demo-title">Pick a call.</span>
              <span className="text-muted">Watch it get caught.</span>
            </MaskLines>
          </div>
          <ul className="flex flex-col gap-3" onPointerEnter={takeOver} onFocus={takeOver} onPointerLeave={() => { if (!auto) setHovered(null) }}>
            {SCENARIOS.map((s, i) => {
              const active = picked === s.id
              return (
                <BlurIn as="li" key={s.id} delay={i * 0.06}>
                  <button
                    ref={el => { cardRefs.current[i] = el }}
                    type="button"
                    onClick={() => { setAuto(false); pick(s.id) }}
                    onPointerEnter={() => setHovered(s.id)}
                    onFocus={() => setHovered(s.id)}
                    onBlur={() => { if (!auto) setHovered(null) }}
                    aria-pressed={active}
                    aria-keyshortcuts={String(i + 1)}
                    className={`group relative flex w-full items-start gap-4 overflow-hidden rounded-2xl border p-5 text-left transition-[border-color,background-color,transform] duration-300 active:scale-[0.99] ${active ? 'border-accent/60 bg-ink-1' : 'border-border bg-background hover:border-[color-mix(in_oklab,var(--accent)_35%,transparent)] hover:bg-ink-1'}`}
                  >
                    {/* A sweep of amber light crosses the card while it runs. */}
                    {active && running && <span className="demo-sweep pointer-events-none absolute inset-0" aria-hidden="true" />}
                    <Eq live={active && running} />
                    <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                      <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <span className="font-medium text-foreground">{s.name}</span>
                        <span className="font-mono text-xs text-muted">{s.language}</span>
                      </span>
                      <span className="line-clamp-1 text-sm text-muted">{s.transcript}</span>
                    </span>
                    <kbd className="hidden shrink-0 rounded-md border border-border px-1.5 font-mono text-xs leading-5 text-muted transition-colors group-hover:border-accent/40 group-hover:text-accent lg:block">{i + 1}</kbd>
                  </button>
                </BlurIn>
              )
            })}
          </ul>
        </div>

        <div className="relative lg:pt-20">
          {/* The bloom under the panel takes the verdict's colour. */}
          <div
            className="pointer-events-none absolute inset-x-[10%] bottom-[8%] top-[30%] -z-10 rounded-full blur-3xl transition-[background-color,opacity] duration-700"
            style={{
              backgroundColor: mode === 'result'
                ? `color-mix(in oklab, var(--${v.tone === 'high' ? 'red-500' : v.tone === 'caution' ? 'yellow-400' : v.tone === 'safe' ? 'mint-400' : 'grey-700'}) 22%, transparent)`
                : 'color-mix(in oklab, var(--accent) 14%, transparent)',
              opacity: mode === 'idle' ? 0.35 : 1,
            }}
            aria-hidden="true"
          />
          <div
            ref={panel}
            className={`glass relative flex min-h-[560px] flex-col overflow-hidden rounded-3xl border transition-colors duration-500 ${tone ? tone.ring : 'border-border'}`}
          >
            <div className="flex items-center justify-between gap-4 px-6 pt-5 sm:px-8">
              <span className={`inline-flex items-center gap-2.5 font-mono text-xs uppercase tracking-[0.08em] ${tone ? tone.text : 'text-muted'}`}>
                {mode !== 'result' && <span className={`size-1.5 rounded-full ${head.dot}`} aria-hidden="true" />}
                {mode === 'result' && <tone.Icon className="size-3.5" aria-hidden="true" />}
                {head.text}
              </span>
              {auto ? (
                <button type="button" onClick={() => setAuto(false)} className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.08em] text-muted transition-colors hover:text-foreground">
                  <span className="tabular">Auto · {autoIndex + 1} / {SCENARIOS.length}</span>
                  <Pause className="size-3.5" aria-hidden="true" />
                  <span className="sr-only">Stop auto-play</span>
                </button>
              ) : (
                <span className="label-mono">Prepared sample</span>
              )}
            </div>
            <div className="relative mt-4 h-[clamp(140px,22vh,184px)] border-y border-hairline">
              <LineScope mode={mode} tone={v?.tone} jitter={focus?.jitter ?? 1} />
              <span className="label-mono absolute bottom-2 left-6 sm:left-8">Heard</span>
              <span className="label-mono absolute bottom-2 right-6 sm:right-8">Incoming</span>
            </div>
            <div className="flex flex-1 flex-col justify-center p-6 sm:p-8">
              <AnimatePresence mode="wait">
                {mode === 'idle' && (
                  <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col gap-4">
                    <p className="font-display text-3xl text-foreground">Waiting for a call</p>
                    <p className="max-w-sm leading-relaxed text-muted">
                      Hover a call to put it on the line, then press it, or <kbd className="rounded border border-border px-1 font-mono text-xs">1</kbd>–<kbd className="rounded border border-border px-1 font-mono text-xs">4</kbd>, to run it through the same pipeline the workspace uses.
                    </p>
                  </motion.div>
                )}
                {mode === 'preview' && (
                  <motion.div key={`pre-${focus.id}`} initial={{ opacity: 0, y: reduce ? 0 : 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }} className="flex flex-col gap-4">
                    <p className="font-display text-3xl text-foreground">{focus.name}</p>
                    <p className="max-w-md text-lg leading-relaxed text-muted" lang={focus.language === 'Hindi' ? 'hi' : undefined}>“{focus.transcript}”</p>
                    <p className="label-mono text-accent">Press to analyze</p>
                  </motion.div>
                )}
                {mode === 'running' && (
                  <motion.div key={`run-${picked}`} initial={{ opacity: 0, y: reduce ? 0 : 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-col gap-8">
                    <p className="label-mono">Analyzing</p>
                    <Stages />
                  </motion.div>
                )}
                {mode === 'result' && <Verdict key={result.session_id} data={result} />}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
