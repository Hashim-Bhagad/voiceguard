import { useRef, useState } from 'react'
import { useAnalysis } from '../lib/AnalysisContext'
import { useRecorder } from '../lib/useRecorder'
import { SCENARIOS } from '../lib/analysis'
import { Icon, Panel, PrivacyBadge, Waveform } from './ui'
import { ScenarioCarousel } from './Carousels'
import { AudioScope } from './SignalGraphics'
const languages = [['auto', 'Auto-detect'], ['auto-hinglish', 'Hinglish · Code-mixed'], ['hi', 'Hindi · हिन्दी'], ['en', 'Indian English'], ['mr', 'Marathi · मराठी'], ['ta', 'Tamil · தமிழ்']]
export default function AudioInput() {
  const { status, data, error, runAnalysis, reset, retry } = useAnalysis()
  const [language, setLanguage] = useState('auto')
  const [showInput, setShowInput] = useState(false)
  const [policy, setPolicy] = useState('standard')
  const [dragging, setDragging] = useState(false)
  const [fileError, setFileError] = useState(null)
  const input = useRef(null)
  const recorder = useRecorder(blob => runAnalysis(blob, { lang: language, policy }))
  const busy = status === 'analyzing'
  const recording = recorder.state === 'recording'
  const locked = busy || recorder.state !== 'idle'
  function upload(file) {
    setFileError(null)
    if (!file || locked) return
    if (!(file.type.startsWith('audio/') || /\.(wav|mp3|m4a|webm|ogg|flac|aac|mp4)$/i.test(file.name))) { setFileError('Choose an audio file: WAV, MP3, M4A, WebM, Ogg, or FLAC.'); return }
    setShowInput(false)
    runAnalysis(file, { lang: language, policy })
  }
  return <Panel title="Analyze a conversation" meta={<span className="badge neutral">AUDIO INPUT</span>} className="input-panel"><div className="input-complete-bar" hidden={!data || showInput}><div><span className="complete-check"><Icon name="check" /></span><span><strong>{data?.name}</strong><small>{data?.source === 'demo' ? 'Prepared scenario · simulated evidence' : 'Recording processed by the analysis service'}</small></span></div><button className="button ghost compact" onClick={() => setShowInput(true)}>Change audio or scenario <Icon name="transfer" size={16} /></button></div><div hidden={Boolean(data) && !showInput}><div className="input-grid"><div className={`upload-zone ${dragging ? 'dragging' : ''} ${busy ? 'analyzing-zone' : ''}`} onDragOver={e => { e.preventDefault(); if (!locked) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files[0]) }}>
    {busy ? <><div className="analysis-indicator"><Waveform active /><span className="scanner-line" /></div><strong role="status">Listening for the signals…</strong><p>Transcribing and evaluating your recording.</p><button className="button compact ghost" onClick={reset}>Cancel analysis</button></> : recording ? <><AudioScope stream={recorder.stream} active /><strong role="status"><span className="record-dot" />Recording · {String(Math.floor(recorder.seconds / 60)).padStart(2, '0')}:{String(recorder.seconds % 60).padStart(2, '0')}</strong><p>Speak clearly. Recording stops after 60 seconds.</p><button className="button danger" onClick={recorder.stop}>Stop & analyze <Icon name="arrow" size={16} /></button></> : <><span className="upload-icon"><Icon name="upload" size={23} /></span><strong>Drop your audio here</strong><p>WAV, MP3, M4A, WebM, Ogg, FLAC · up to 25 MB</p><div className="input-actions"><button className="button" onClick={() => input.current?.click()} disabled={locked}>Choose a file <Icon name="upload" size={15} /></button><span>or</span><button className="button ghost" onClick={recorder.start} disabled={locked}><Icon name="mic" size={16} />{recorder.state === 'requesting' ? 'Allow microphone…' : 'Record audio'}</button></div></>}
    <input ref={input} type="file" accept="audio/*,.webm,.m4a" aria-label="Choose audio recording" hidden onChange={e => { upload(e.target.files?.[0]); e.target.value = '' }} /></div><div className="input-settings"><label htmlFor="language">Conversation language</label><select id="language" value={language} disabled={locked} onChange={e => setLanguage(e.target.value)}>{languages.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select><p>A transcription hint; availability depends on your analysis service.</p><label htmlFor="policy">Analysis profile</label><select id="policy" value={policy} disabled={locked} onChange={e => setPolicy(e.target.value)}><option value="standard">Standard conversation</option><option value="high-value-txn">High-value transaction</option></select><PrivacyBadge attestation={data?.source === 'live' ? data.privacy_attestation : null} /></div></div>
    {(error || fileError || recorder.error) && <div className="notice error-notice" role="alert"><Icon name="alert" /><div><strong>We couldn’t complete that recording.</strong><p>{fileError || recorder.error || error}</p>{status === 'error' && <button className="button compact" onClick={retry}>Retry analysis</button>}</div></div>}
    <div className="scenario-section"><div className="scenario-heading"><span>Explore a prepared scenario</span><span className="muted small">Demo data · no upload needed</span></div><ScenarioCarousel disabled={locked} onSelect={id => { setFileError(null); setShowInput(false); runAnalysis(id) }} /><div className="scenario-buttons">{SCENARIOS.map(s => <button key={s.id} disabled={locked} className={`scenario-button ${data?.name === s.short ? 'selected' : ''}`} onClick={() => { setFileError(null); setShowInput(false); runAnalysis(s.id) }}><Icon name={s.icon} size={16} />{s.short}<Icon name="chevron" size={13} /></button>)}</div></div></div></Panel>
}
