import { useEffect, useState } from 'react'
import { Alert, Button, Spinner } from '@heroui/react'
import { Check } from 'lucide-react'
import { useAnalysis } from '@/lib/AnalysisContext'
import { useBackend } from '@/lib/backend'

const STEPS = [
  { label: 'Uploading audio', at: 0 },
  { label: 'Transcribing speech', at: 1.5 },
  { label: 'Acoustic scan (XLS-R + AASIST)', at: 3.5 },
  { label: 'Fusing signals into one score', at: 6 },
]

function useElapsed(since, active) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(t)
  }, [active])
  return since ? Math.max(0, (now - since) / 1000) : 0
}

// Steps advance on typical timings, and the copy says so: the service returns
// one response, so nothing here pretends to measure the stages.
export function Pipeline({ onSample }) {
  const { status, startedAt } = useAnalysis()
  const backend = useBackend()
  const elapsed = useElapsed(startedAt, status === 'analyzing')
  const current = STEPS.reduce((n, s, i) => (elapsed >= s.at ? i : n), 0)
  const waking = elapsed > 3 && backend.status !== 'ready'

  return (
    <section aria-busy="true" className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-base font-medium">Analyzing the call</h2>
        <span className="font-mono text-sm text-muted tabular" aria-hidden="true">{elapsed.toFixed(0)}s</span>
      </div>
      <p className="sr-only" role="status">{STEPS[current].label}</p>
      <ol className="flex flex-col gap-3">
        {STEPS.map((step, i) => {
          const done = i < current
          const active = i === current
          return (
            <li key={step.label} aria-current={active ? 'step' : undefined} className={`flex items-center gap-3 text-sm transition-colors ${active ? 'text-foreground' : done ? 'text-muted' : 'text-muted/50'}`}>
              <span className="grid size-5 place-items-center">
                {done ? <Check aria-hidden className="size-4 text-success" /> : active ? <Spinner size="sm" /> : <span className="size-1.5 rounded-full bg-current" />}
              </span>
              {step.label}
              <span className="sr-only">{done ? ', done' : active ? ', in progress' : ''}</span>
            </li>
          )
        })}
      </ol>
      <p className="text-xs text-muted">Steps follow typical timings. The result arrives all at once.</p>
      {waking && (
        <Alert status="warning">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>Waking the model</Alert.Title>
            <Alert.Description>The server sleeps when nobody is using it. The first analysis can take up to 30 seconds while the model loads.</Alert.Description>
          </Alert.Content>
        </Alert>
      )}
      {elapsed > 15 && onSample && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-muted">Still working. You can stop and look at a prepared example instead.</span>
          <Button size="sm" variant="secondary" onPress={onSample}>Show a sample result instead</Button>
        </div>
      )}
    </section>
  )
}

const ERROR_VIEW = {
  timeout: { title: 'That took too long', action: 'Retry', retry: true },
  offline: { title: 'Could not reach the analysis service', action: 'Try a sample call', retry: false },
  server: { title: 'The service returned an error', action: 'Retry', retry: true },
  input: { title: 'This recording could not be analyzed', action: 'Choose another recording', retry: false },
}

export function ErrorPanel({ onSample, onReset }) {
  const { error, retry } = useAnalysis()
  if (!error) return null
  const view = ERROR_VIEW[error.kind] || ERROR_VIEW.input
  const act = view.retry ? retry : error.kind === 'offline' ? onSample : onReset
  return (
    <Alert status="danger" role="alert">
      <Alert.Indicator />
      <Alert.Content>
        <Alert.Title>{view.title}</Alert.Title>
        <Alert.Description>
          {error.message}
          {error.kind === 'offline' && ' Sample calls still work without the service.'}
          {error.kind === 'input' && ' Use at least 3 seconds of clear speech.'}
        </Alert.Description>
        <Button className="mt-3 w-fit" size="sm" variant="secondary" onPress={act}>{view.action}</Button>
      </Alert.Content>
    </Alert>
  )
}
