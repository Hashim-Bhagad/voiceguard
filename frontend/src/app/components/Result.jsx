import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import NumberFlow from '@number-flow/react'
import { Accordion, Button, Chip } from '@heroui/react'
import { ArrowRight, Check, Copy, RotateCcw } from 'lucide-react'
import { explain, markTranscript } from '@/lib/explain'
import { ButtonLink, SourceChip } from './ui'
import { TONES } from '../tones'

const EASE = [0.16, 1, 0.3, 1]
const pts = v => (Number.isFinite(v) ? `+${(v * 100).toFixed(1)}` : 'n/a')
const pc = v => (Number.isFinite(v) ? `${Math.round(v * 100)}%` : 'n/a')
const TONE_VAR = { high: '--red-500', caution: '--yellow-400', safe: '--mint-400', neutral: '--grey-700' }
// Contribution colours: evidence in the accent ramp, settings in grey.
const PART_COLOR = { acoustic: 'var(--accent)', linguistic: 'var(--amber-600)', context: 'var(--grey-700)', prosody: 'var(--muted)' }

export function VerdictCard({ data, onReset }) {
  const e = explain(data)
  const tone = TONES[e.tone] || TONES.neutral
  const Icon = tone.Icon
  const score = Math.round((data.final_risk_score || 0) * 100)
  const [shown, setShown] = useState(0)
  useEffect(() => { const id = requestAnimationFrame(() => setShown(score)); return () => cancelAnimationFrame(id) }, [score])
  const headline = { high: 'Pause. This call needs verifying.', caution: 'Proceed carefully.', safe: 'Nothing alarming in this call.' }[e.tone] || 'Not enough to go on.'

  return (
    <motion.section
      initial={{ opacity: 0, y: 16, filter: 'blur(6px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ duration: 0.6, ease: EASE }}
      aria-labelledby="verdict-title"
      className="glass relative isolate overflow-hidden rounded-2xl p-6 sm:p-8"
    >
      {/* The verdict colour blooms from behind the score. */}
      <div
        className="pointer-events-none absolute -right-24 -top-24 -z-10 size-[28rem] rounded-full blur-3xl"
        style={{ background: `radial-gradient(closest-side, color-mix(in oklab, var(${TONE_VAR[e.tone] || TONE_VAR.neutral}) 26%, transparent), transparent)` }}
        aria-hidden="true"
      />
      <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
        <div className="flex max-w-xl flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Chip color={tone.color} variant="soft" size="sm">
              <Icon aria-hidden className="size-3.5" />
              <Chip.Label>{e.label}</Chip.Label>
            </Chip>
            <SourceChip source={data.source} />
          </div>
          <h2 id="verdict-title" className="text-[clamp(1.5rem,2.6vw,2rem)] font-semibold leading-tight tracking-[-0.02em]">{headline}</h2>
          <p className="text-[0.975rem] leading-relaxed text-muted">{e.summary}</p>
          <div className="mt-1 flex flex-col gap-1 border-l-2 pl-4" style={{ borderColor: `var(${TONE_VAR[e.tone] || TONE_VAR.neutral})` }}>
            <p className="text-sm font-medium text-foreground">{e.action.title}</p>
            <p className="text-sm leading-relaxed text-muted">{e.action.text}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-2">
            {data.challenge_triggered && data.quality !== 'insufficient'
              ? <ButtonLink to="/dashboard/challenge" variant="primary">Verify the caller <ArrowRight aria-hidden className="size-4" /></ButtonLink>
              : <Button variant="secondary" onPress={onReset}><RotateCcw aria-hidden className="size-4" />Analyze another</Button>}
            {data.challenge_triggered && <Button variant="ghost" onPress={onReset}>Analyze another</Button>}
          </div>
        </div>
        <div className="flex flex-col items-start gap-1 md:items-end">
          <span className="label-mono">Combined risk</span>
          <span className={`font-pixel text-[clamp(4rem,9vw,6.5rem)] leading-none tabular ${tone.text}`} role="img" aria-label={`${score} percent`}>
            <NumberFlow value={shown} transformTiming={{ duration: 1000, easing: 'cubic-bezier(.16,1,.3,1)' }} />
            <span className="text-[0.45em] text-muted">%</span>
          </span>
          {Number.isFinite(data.acoustic_risk_score) && (
            <span className="font-mono text-xs text-muted">Voice spoof score {data.acoustic_risk_score.toFixed(3)}</span>
          )}
        </div>
      </div>
    </motion.section>
  )
}

// The score as a strip of 50 cells (2 points each), filled by what each signal added,
// with the standard policy's review and hold lines marked on it.
function ScoreStrip({ parts, final }) {
  const cells = 50
  let filled = 0
  const owner = []
  for (const p of parts) {
    const n = Number.isFinite(p.points) ? Math.round(p.points * cells) : 0
    for (let i = 0; i < n && filled < cells; i++, filled++) owner.push(p.key)
  }
  const target = Math.min(cells, Math.round((final || 0) * cells))
  while (owner.length < target) owner.push('smoothing')
  owner.length = Math.min(owner.length, target)
  return (
    <div className="relative pt-6">
      <div className="grid grid-cols-[repeat(50,minmax(0,1fr))] gap-[3px]" aria-hidden="true">
        {Array.from({ length: cells }, (_, i) => (
          <motion.span
            key={i}
            className="aspect-[1/2.2] rounded-[2px]"
            initial={{ opacity: 0, scaleY: 0.3 }}
            animate={{ opacity: 1, scaleY: 1 }}
            transition={{ delay: 0.25 + i * 0.012, duration: 0.25 }}
            style={{ background: owner[i] ? (PART_COLOR[owner[i]] || 'var(--paper)') : 'color-mix(in oklab, var(--foreground) 7%, transparent)' }}
          />
        ))}
      </div>
      {[{ at: 0.35, label: 'Review 35' }, { at: 0.55, label: 'Hold 55' }].map(t => (
        <span key={t.at} className="absolute top-0 flex -translate-x-1/2 flex-col items-center gap-1" style={{ left: `${t.at * 100}%` }} aria-hidden="true">
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.06em] text-muted">{t.label}</span>
          <span className="h-[calc(100%+0.5rem)] w-px bg-hairline" />
        </span>
      ))}
    </div>
  )
}

function ScoreBuild({ e, data }) {
  return (
    <section aria-labelledby="build-title" className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id="build-title" className="text-base font-medium">What the score is made of</h3>
        <span className="text-xs text-muted">Lines show the standard policy’s thresholds</span>
      </div>
      <ScoreStrip parts={e.contributions} final={data.final_risk_score} />
      <ul className="flex flex-col divide-y divide-hairline">
        {e.contributions.map(p => (
          <li key={p.key} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 py-3.5">
            <span className="size-2.5 rounded-[2px]" style={{ background: PART_COLOR[p.key] }} aria-hidden="true" />
            <span className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-sm font-medium text-foreground">{p.label}</span>
              <span className="text-sm text-muted">{p.what}</span>
              <span className={`rounded border px-1.5 font-mono text-[0.65rem] uppercase leading-5 tracking-[0.05em] ${p.kind === 'evidence' ? 'border-accent/30 text-accent' : 'border-border text-muted'}`}>{p.basis}</span>
            </span>
            <span className="text-right font-mono text-sm tabular">
              {p.score !== null && <span className="text-muted">{pc(p.score)} × {p.weight?.toFixed(2)} = </span>}
              <span className="text-foreground">{pts(p.points)}</span>
            </span>
          </li>
        ))}
        {Math.abs(e.smoothing) > 0.005 && (
          <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 py-3.5">
            <span className="size-2.5 rounded-[2px] bg-paper" aria-hidden="true" />
            <span className="text-sm text-muted">Smoothing with earlier scores in this session</span>
            <span className="font-mono text-sm tabular text-foreground">{e.smoothing >= 0 ? '+' : ''}{(e.smoothing * 100).toFixed(1)}</span>
          </li>
        )}
        <li className="flex items-baseline justify-between gap-4 pt-4">
          <span className="text-sm text-muted">Combined risk</span>
          <span className="font-mono text-base tabular text-foreground">{pc(data.final_risk_score)}</span>
        </li>
      </ul>
      {e.primary === 'acoustic_model' && (
        <p className="text-xs leading-relaxed text-muted">The voice model is the only signal validated on held-out data. Words and policy add context; they cannot show the voice is cloned.</p>
      )}
    </section>
  )
}

// Where in the call the voice sounded synthetic: one column per 4-second window the
// model scored (they overlap by half). The clip score is the mean of these.
function Timeline({ segments }) {
  const end = Math.max(...segments.map(s => s.end_s))
  const rows = 10
  return (
    <section aria-labelledby="timeline-title" className="flex flex-col gap-5 rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id="timeline-title" className="text-base font-medium">Where in the call</h3>
        <span className="text-xs text-muted">Each column is one 4-second window the voice model scored</span>
      </div>
      <div className="relative h-36" role="img" aria-label={segments.map(s => `${s.start_s}s to ${s.end_s}s: ${Math.round(s.spoof_score * 100)}% synthetic`).join('; ')}>
        <span className="absolute inset-x-0 border-t border-dashed border-hairline" style={{ bottom: '50%' }} aria-hidden="true" />
        <span className="label-mono absolute right-0 -translate-y-full pb-1" style={{ bottom: '50%' }} aria-hidden="true">50%</span>
        {segments.map((s, i) => {
          const mid = (s.start_s + s.end_s) / 2
          const lit = Math.max(1, Math.round(s.spoof_score * rows))
          const synthetic = s.spoof_score >= 0.5
          return (
            <div key={i} className="absolute bottom-0 flex -translate-x-1/2 flex-col-reverse gap-[3px]" style={{ left: `${(mid / end) * 100}%`, width: `${Math.max(4, 70 / segments.length)}%` }} aria-hidden="true">
              {Array.from({ length: rows }, (_, r) => (
                <motion.span
                  key={r}
                  className="h-[11px] rounded-[2px]"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.2 + i * 0.06 + r * 0.02 }}
                  style={{ background: r < lit ? (synthetic ? 'var(--red-500)' : 'var(--mint-400)') : 'color-mix(in oklab, var(--foreground) 6%, transparent)' }}
                />
              ))}
            </div>
          )
        })}
      </div>
      <div className="flex justify-between font-mono text-xs text-muted tabular" aria-hidden="true">
        <span>0s</span><span>{end.toFixed(1)}s</span>
      </div>
      <p className="text-xs leading-relaxed text-muted">Red columns score above 50% synthetic. A clone spliced into part of a call shows up as a run of red among green.</p>
    </section>
  )
}

function WhatWasSaid({ e, data }) {
  const runs = markTranscript(data.transcript, e.hits)
  return (
    <section aria-labelledby="said-title" className="flex flex-col gap-5 rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 id="said-title" className="text-base font-medium">What was said</h3>
        <span className="text-xs text-muted">
          {data.source === 'demo' ? 'Prepared transcript' : 'Transcribed by Whisper'}
          {e.language && ` · ${e.language}`}
        </span>
      </div>
      <blockquote className="text-[1.1rem] leading-[1.75] text-foreground">
        {data.transcript ? (
          <>“{runs.map((r, i) => r.hit
            ? <mark key={i} className="rounded-[3px] bg-[color-mix(in_oklab,var(--amber-600)_22%,transparent)] px-0.5 text-foreground underline decoration-amber-hot decoration-2 underline-offset-4" title={r.hit.category || 'Pressure cue'}>{r.text}</mark>
            : <span key={i}>{r.text}</span>)}”</>
        ) : 'No transcript was returned for this recording.'}
      </blockquote>
      {e.hits.length > 0 ? (
        <ul className="flex flex-wrap gap-2" aria-label="Pressure cues found">
          {e.hits.map(h => (
            <li key={h.keyword} className="inline-flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5 text-xs">
              <span className="font-medium text-foreground">{h.keyword}</span>
              {h.category && <span className="text-muted">{h.category}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">No pressure or secrecy cues matched the lexicons (English, Hindi, Hinglish, Marathi, Tamil).</p>
      )}
    </section>
  )
}

function Unused({ e }) {
  return (
    <Accordion allowsMultipleExpanded className="rounded-2xl border border-border bg-surface px-2">
      <Accordion.Item id="markers">
        <Accordion.Heading>
          <Accordion.Trigger>Measured, not used in the verdict<Accordion.Indicator /></Accordion.Trigger>
        </Accordion.Heading>
        <Accordion.Panel>
          <Accordion.Body className="flex flex-col gap-4 pb-5">
            <p className="text-sm leading-relaxed text-muted">
              The service measures these forensic markers too, but on held-out clips they do not separate real voices from clones, so they do not move the score.
            </p>
            <dl className="grid gap-3 sm:grid-cols-3">
              {e.markers.map(m => (
                <div key={m.key} className="flex flex-col gap-1.5 rounded-xl border border-border p-4">
                  <dt className="text-xs text-muted">{m.label}</dt>
                  <dd className="font-mono text-lg tabular text-foreground/70">{m.value ?? 'Not returned'}</dd>
                  <dd className="text-xs leading-relaxed text-muted">{m.note}</dd>
                </div>
              ))}
            </dl>
          </Accordion.Body>
        </Accordion.Panel>
      </Accordion.Item>
      {e.notes.length > 0 && (
        <Accordion.Item id="notes">
          <Accordion.Heading>
            <Accordion.Trigger>The service’s raw notes<Accordion.Indicator /></Accordion.Trigger>
          </Accordion.Heading>
          <Accordion.Panel>
            <Accordion.Body className="pb-5">
              <ul className="flex flex-col gap-2 text-sm leading-relaxed text-muted">
                {e.notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </Accordion.Body>
          </Accordion.Panel>
        </Accordion.Item>
      )}
    </Accordion>
  )
}

export default function Result({ data, onReset }) {
  const ref = useRef(null)
  const [copied, setCopied] = useState(false)
  const e = explain(data)
  useEffect(() => { ref.current?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' }) }, [data.session_id])

  async function copy() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      setCopied(true); setTimeout(() => setCopied(false), 1800)
    } catch { /* clipboard blocked */ }
  }

  return (
    <div ref={ref} className="flex scroll-mt-24 flex-col gap-6">
      <VerdictCard data={data} onReset={onReset} />
      {e.segments.length > 1 && <Timeline segments={e.segments} />}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <ScoreBuild e={e} data={data} />
        <WhatWasSaid e={e} data={data} />
      </div>
      <Unused e={e} />
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
        <span>
          A risk signal, not proof of identity.
          {e.modelVer && data.source !== 'demo' && ` Model ${e.modelVer}.`}
          {e.measuredOn && ` Marker reliability measured on ${e.measuredOn}.`}
        </span>
        <Button size="sm" variant="ghost" onPress={copy}>
          {copied ? <Check aria-hidden className="size-3.5 text-success" /> : <Copy aria-hidden className="size-3.5" />}
          {copied ? 'Copied' : 'Copy result JSON'}
        </Button>
      </div>
    </div>
  )
}
