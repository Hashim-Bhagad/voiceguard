import { useRef, useState } from 'react'
import { Button, Chip, Disclosure, Label, ListBox, Select, Tabs } from '@heroui/react'
import { ArrowRightLeft, AudioLines, ChevronRight, FileAudio, KeyRound, Mic, ShieldCheck, Square, Upload } from 'lucide-react'
import { SCENARIOS } from '@/lib/analysis'
import { useAnalysis } from '@/lib/AnalysisContext'
import { useRecorder } from '@/lib/useRecorder'
import { wakeBackend } from '@/lib/backend'
import AudioScope from './AudioScope'

const SCENARIO_ICON = { transfer: ArrowRightLeft, lock: KeyRound, shield: ShieldCheck, wave: AudioLines }
const LANGUAGES = [
  ['auto', 'Detect automatically'],
  ['auto-hinglish', 'Hinglish (code-mixed)'],
  ['hi', 'Hindi'],
  ['en', 'Indian English'],
  ['bn', 'Bengali'],
  ['mr', 'Marathi'],
  ['ta', 'Tamil'],
]
const POLICIES = [
  ['standard', 'Standard'],
  ['high-value-txn', 'High-value transaction (stricter)'],
]
const AUDIO_EXT = /\.(wav|mp3|m4a|webm|ogg|oga|opus|flac|aac|mp4)$/i
const MIN_SECONDS = 3

function Picker({ label, value, onChange, options }) {
  return (
    <Select className="w-full sm:w-64" selectedKey={value} onSelectionChange={key => onChange(String(key))}>
      <Label>{label}</Label>
      <Select.Trigger>
        <Select.Value />
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover>
        <ListBox>
          {options.map(([id, text]) => (
            <ListBox.Item key={id} id={id} textValue={text}>
              {text}
              <ListBox.ItemIndicator />
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select>
  )
}

function SampleCalls({ busy, onPick, onHover }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2" aria-label="Sample calls">
      {SCENARIOS.map(s => {
        const Icon = SCENARIO_ICON[s.icon] || AudioLines
        return (
          <li key={s.id}>
            <button
              type="button"
              disabled={busy}
              onClick={() => onPick(s.id)}
              onPointerEnter={() => onHover?.(s.id)}
              onPointerLeave={() => onHover?.(null)}
              onFocus={() => onHover?.(s.id)}
              onBlur={() => onHover?.(null)}
              className="group flex h-full w-full flex-col gap-3 rounded-xl border border-border bg-ink-0 p-4 text-left transition-[border-color,background-color,transform] duration-200 hover:border-accent/40 hover:bg-ink-1 active:scale-[0.99] disabled:pointer-events-none disabled:opacity-50"
            >
              <span className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2.5 text-sm font-medium text-foreground">
                  <Icon aria-hidden className="size-4 text-muted transition-colors group-hover:text-accent" strokeWidth={1.75} />
                  {s.name}
                </span>
                <Chip size="sm" variant="secondary"><Chip.Label>{s.language}</Chip.Label></Chip>
              </span>
              <span className="line-clamp-2 text-[0.85rem] leading-relaxed text-muted">“{s.transcript}”</span>
              <span className="mt-auto inline-flex items-center gap-1 text-xs font-medium text-muted transition-colors group-hover:text-accent">
                Analyze this call <ChevronRight aria-hidden className="size-3.5 transition-transform group-hover:translate-x-0.5" />
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function UploadZone({ busy, onFile }) {
  const input = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [problem, setProblem] = useState(null)
  const [picked, setPicked] = useState(null)

  function take(file) {
    setProblem(null)
    if (!file || busy) return
    if (!(file.type.startsWith('audio/') || file.type === 'video/mp4' || AUDIO_EXT.test(file.name))) {
      setProblem(`“${file.name}” is not an audio file. Use WAV, MP3, M4A, WebM, Ogg or FLAC.`)
      return
    }
    if (file.size === 0) { setProblem('That file is empty. Choose another recording.'); return }
    if (file.size > 25 * 1024 * 1024) { setProblem(`That file is ${(file.size / 1048576).toFixed(1)} MB. The limit is 25 MB; trim it or export at a lower bitrate.`); return }
    setPicked(file.name)
    onFile(file)
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        role="button"
        tabIndex={busy ? -1 : 0}
        aria-disabled={busy}
        aria-describedby="upload-help"
        onClick={() => !busy && input.current?.click()}
        onKeyDown={e => { if ((e.key === 'Enter' || e.key === ' ') && !busy) { e.preventDefault(); input.current?.click() } }}
        onPointerEnter={wakeBackend}
        onFocus={wakeBackend}
        onDragEnter={wakeBackend}
        onDragOver={e => { e.preventDefault(); if (!busy) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); take(e.dataTransfer.files?.[0]) }}
        className={`flex min-h-44 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center transition-colors ${dragging ? 'border-accent bg-accent/5' : 'border-border bg-ink-0 hover:border-muted/60'} ${busy ? 'pointer-events-none opacity-50' : ''}`}
      >
        <span className="grid size-11 place-items-center rounded-full bg-default">
          {picked ? <FileAudio aria-hidden className="size-5 text-accent" /> : <Upload aria-hidden className="size-5 text-muted" />}
        </span>
        <span className="text-sm font-medium text-foreground">{picked ? picked : dragging ? 'Drop to analyze' : 'Drop a recording here, or choose a file'}</span>
        <span id="upload-help" className="text-xs text-muted">WAV, MP3, M4A, WebM, Ogg or FLAC, up to 25 MB. At least 3 seconds of speech.</span>
      </div>
      <input ref={input} type="file" accept="audio/*,.m4a,.webm,.ogg,.flac,.mp4" className="sr-only" tabIndex={-1} aria-hidden onChange={e => { take(e.target.files?.[0]); e.target.value = '' }} />
      {problem && <p role="alert" className="text-sm text-danger">{problem}</p>}
    </div>
  )
}

function RecordPanel({ busy, onBlob }) {
  const recorder = useRecorder(blob => onBlob(blob))
  const recording = recorder.state === 'recording'
  const canStop = recording && recorder.seconds >= MIN_SECONDS

  function toggle() {
    if (busy) return
    if (recording) { if (canStop) recorder.stop() }
    else if (recorder.state === 'idle') recorder.start()
  }

  return (
    <div
      className="flex flex-col gap-4 rounded-xl"
      tabIndex={-1}
      onKeyDown={e => { if (e.code === 'Space' && e.target === e.currentTarget) { e.preventDefault(); toggle() } }}
    >
      {recording ? <AudioScope stream={recorder.stream} /> : (
        <div className="flex h-24 items-center rounded-lg bg-ink-0 px-4 text-sm text-muted">
          Read a sentence or two aloud, or hold your phone's speaker to the microphone during a call.
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {recording ? (
          <Button variant="primary" onPress={recorder.stop} isDisabled={!canStop}>
            <Square aria-hidden className="size-3.5 fill-current" />
            {canStop ? 'Stop and analyze' : `Keep talking · ${MIN_SECONDS - recorder.seconds}s`}
          </Button>
        ) : (
          <Button variant="primary" onHoverStart={wakeBackend} onFocus={wakeBackend} onPress={() => { wakeBackend(); recorder.start() }} isDisabled={busy || recorder.state === 'requesting'}>
            <Mic aria-hidden className="size-4" />
            {recorder.state === 'requesting' ? 'Allow microphone access' : 'Start recording'}
          </Button>
        )}
        <span className="font-mono text-sm text-muted tabular" aria-live="polite">
          {recording ? `0:${String(recorder.seconds).padStart(2, '0')} / 1:00` : 'Up to 60 seconds'}
        </span>
      </div>
      {recorder.error && <p role="alert" className="text-sm text-danger">{recorder.error}</p>}
      <p className="text-xs text-muted">Audio stays in this browser until you stop; then it is sent once for analysis.</p>
    </div>
  )
}

export default function InputCard({ onHover }) {
  const { status, runAnalysis } = useAnalysis()
  const [tab, setTab] = useState('samples')
  const [lang, setLang] = useState('auto')
  const [policy, setPolicy] = useState('standard')
  const busy = status === 'analyzing'
  const live = input => runAnalysis(input, { lang, policy })

  return (
    <section aria-label="Choose audio to analyze" className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <Tabs selectedKey={tab} onSelectionChange={key => { setTab(String(key)); if (key !== 'samples') wakeBackend() }} className="w-full">
        <Tabs.ListContainer>
          <Tabs.List aria-label="Audio source" className="w-full sm:w-auto">
            <Tabs.Tab className="whitespace-nowrap" id="samples">Sample calls<Tabs.Indicator /></Tabs.Tab>
            <Tabs.Tab className="whitespace-nowrap" id="upload">Upload<Tabs.Indicator /></Tabs.Tab>
            <Tabs.Tab className="whitespace-nowrap" id="record">Record<Tabs.Indicator /></Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>
        <Tabs.Panel id="samples" className="pt-6">
          <SampleCalls busy={busy} onPick={id => runAnalysis(id)} onHover={onHover} />
          <p className="mt-4 text-xs text-muted">Sample calls use prepared transcripts and scores so you can see the full result without a recording.</p>
        </Tabs.Panel>
        <Tabs.Panel id="upload" className="pt-6"><UploadZone busy={busy} onFile={live} /></Tabs.Panel>
        <Tabs.Panel id="record" className="pt-6"><RecordPanel busy={busy} onBlob={live} /></Tabs.Panel>
      </Tabs>

      {tab !== 'samples' && (
        <Disclosure>
          <Disclosure.Heading>
            <Button slot="trigger" variant="ghost" size="sm" className="-ml-2 text-muted">
              Advanced options
              <Disclosure.Indicator />
            </Button>
          </Disclosure.Heading>
          <Disclosure.Content>
            <Disclosure.Body className="flex flex-col gap-4 pt-3 sm:flex-row">
              <Picker label="Language hint" value={lang} onChange={setLang} options={LANGUAGES} />
              <Picker label="Policy profile" value={policy} onChange={setPolicy} options={POLICIES} />
            </Disclosure.Body>
          </Disclosure.Content>
        </Disclosure>
      )}
    </section>
  )
}
