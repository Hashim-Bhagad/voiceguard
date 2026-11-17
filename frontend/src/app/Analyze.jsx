import { useState } from 'react'
import { useAnalysis } from '@/lib/AnalysisContext'
import { SCENARIOS, verdict } from '@/lib/analysis'
import LineScope from '@/landing/LineScope'
import { PageHeader } from './components/ui'
import InputCard from './components/InputCard'
import { ErrorPanel, Pipeline } from './components/Progress'
import Result from './components/Result'
import { TONES } from './tones'

// The line: the same instrument as the landing demo, so the workspace has a pulse.
// It hisses while idle, carries a sample's voice on hover, heats while analyzing and
// takes the verdict's colour when the result lands.
function Line({ hovered }) {
  const { status, data } = useAnalysis()
  const scenario = SCENARIOS.find(s => s.id === hovered)
  const mode = status === 'analyzing' ? 'running' : status === 'complete' && data ? 'result' : scenario ? 'preview' : 'idle'
  const v = data ? verdict(data) : null
  const tone = mode === 'result' ? TONES[v.tone] || TONES.neutral : null
  const text = {
    idle: 'Line open · choose a call below',
    preview: `On the line · ${scenario?.name ?? ''}`,
    running: 'Listening',
    result: `${v?.label ?? ''} · ${data?.name ?? ''}`,
  }[mode]
  return (
    <div className={`glass relative overflow-hidden rounded-2xl border transition-colors duration-500 ${mode === 'result' && v ? '' : 'border-border'}`}>
      <div className="flex items-center justify-between gap-4 px-5 pt-4 sm:px-6">
        <span className={`inline-flex min-w-0 items-center gap-2.5 truncate font-mono text-xs uppercase tracking-[0.08em] ${tone ? tone.text : 'text-muted'}`}>
          <span className={`size-1.5 shrink-0 rounded-full ${mode === 'idle' ? 'bg-grey-700' : mode === 'running' ? 'animate-pulse bg-amber-hot' : mode === 'preview' ? 'bg-accent' : 'bg-current'}`} aria-hidden="true" />
          <span className="truncate">{text}</span>
        </span>
        <span className="label-mono hidden sm:inline">Heard · Incoming</span>
      </div>
      <div className="mt-3 h-24 sm:h-28">
        <LineScope mode={mode} tone={v?.tone} jitter={scenario?.jitter ?? (data?.acoustic_risk_score >= 0.5 ? 0.1 : 1)} />
      </div>
    </div>
  )
}

export default function Analyze() {
  const { status, data, reset, runAnalysis } = useAnalysis()
  const [hovered, setHovered] = useState(null)
  const sample = () => runAnalysis('synthetic_clone', { instant: true })
  const fresh = () => { reset(); window.scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }) }

  return (
    <div className="flex flex-col gap-10">
      <PageHeader title="Analyze a call">
        Pick a sample call, upload a recording, or record one now. You get a verdict, the words that raised it, and exactly what built the score.
      </PageHeader>
      <div className="flex flex-col gap-4">
        <Line hovered={hovered} />
        <InputCard onHover={setHovered} />
      </div>
      <p className="sr-only" role="status">
        {status === 'complete' && data ? `Analysis complete. ${verdict(data).label}, ${Math.round((data.final_risk_score || 0) * 100)} percent combined risk.` : ''}
      </p>
      {status === 'analyzing' && <Pipeline onSample={sample} />}
      {status === 'error' && <ErrorPanel onSample={sample} onReset={fresh} />}
      {status === 'complete' && data && <Result key={data.session_id} data={data} onReset={fresh} />}
    </div>
  )
}
