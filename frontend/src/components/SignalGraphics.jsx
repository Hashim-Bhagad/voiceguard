import { useEffect, useRef, useState } from 'react'
import { motion, useInView, useReducedMotion } from 'motion/react'
import { Icon } from './ui'
import { percent } from '../lib/analysis'

export function AudioScope({ stream, active = false }) {
  const canvas = useRef(null)
  const [unavailable, setUnavailable] = useState(false)
  useEffect(() => {
    if (!stream || !canvas.current) return
    const context = new AudioContext()
    const analyser = context.createAnalyser()
    analyser.fftSize = 256
    const source = context.createMediaStreamSource(stream)
    source.connect(analyser)
    const values = new Uint8Array(analyser.frequencyBinCount)
    const node = canvas.current
    const brush = node.getContext('2d')
    let frame
    let disposed = false
    let last = 0
    function draw(now) {
      if (disposed) return
      frame = requestAnimationFrame(draw)
      if (document.hidden || now - last < 32) return
      last = now
      const width = node.clientWidth, height = node.clientHeight
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      if (node.width !== width * ratio || node.height !== height * ratio) { node.width = width * ratio; node.height = height * ratio }
      brush.setTransform(ratio, 0, 0, ratio, 0, 0)
      brush.clearRect(0, 0, width, height)
      analyser.getByteFrequencyData(values)
      const bars = 48, gap = 3, barWidth = Math.max(2, width / bars - gap)
      for (let i = 0; i < bars; i++) {
        const level = values[Math.floor(i * values.length / bars)] / 255
        const h = Math.max(3, level * height * .9)
        brush.fillStyle = `rgba(165,235,206,${.35 + level * .65})`
        brush.fillRect(i * (barWidth + gap), (height - h) / 2, barWidth, h)
      }
    }
    context.resume().then(() => { if (!disposed) frame = requestAnimationFrame(draw) }).catch(() => { if (!disposed) setUnavailable(true) })
    return () => { disposed = true; cancelAnimationFrame(frame); source.disconnect(); analyser.disconnect(); void context.close() }
  }, [stream])
  return <div className={`audio-scope ${active ? 'recording-scope' : ''}`}><div className="scope-grid" aria-hidden="true" /><canvas ref={canvas} aria-label={stream ? 'Live microphone frequency levels' : 'Microphone visualization awaiting a recording'} /><span className="scope-label">{unavailable ? 'VISUALIZATION UNAVAILABLE · RECORDING CONTINUES' : active ? 'LIVE MICROPHONE INPUT' : 'WAITING FOR AUDIO'}</span></div>
}
export function RiskGauge({ value = 0, tone = 'safe', label = 'Combined risk', scores = null }) {
  const ref = useRef(null)
  const visible = useInView(ref, { once: true })
  const reduced = useReducedMotion()
  const safeValue = Math.max(0, Math.min(1, value))
  const circumference = 2 * Math.PI * 78

  const hasContrib = Boolean(scores && (scores.acoustic !== undefined || scores.linguistic !== undefined || scores.context !== undefined))
  const acVal = scores?.acoustic != null ? Math.max(0, Math.min(1, scores.acoustic)) : 0
  const liVal = scores?.linguistic != null ? Math.max(0, Math.min(1, scores.linguistic)) : 0
  const cxVal = scores?.context != null ? Math.max(0, Math.min(1, scores.context)) : 0

  const circAc = 2 * Math.PI * 66
  const circLi = 2 * Math.PI * 57
  const circCx = 2 * Math.PI * 49

  return <div className={`risk-gauge tone-${tone}`} ref={ref} role="img" aria-label={`${label}: ${percent(safeValue)}`}><svg viewBox="0 0 200 200" aria-hidden="true"><circle className="gauge-outer" cx="100" cy="100" r="92" /><circle className="gauge-track" cx="100" cy="100" r="78" /><motion.circle className="gauge-value" cx="100" cy="100" r="78" strokeDasharray={circumference} initial={{ strokeDashoffset: circumference }} animate={{ strokeDashoffset: visible ? circumference * (1 - safeValue * .83) : circumference }} transition={{ duration: reduced ? 0 : 1, ease: [.22, 1, .36, 1] }} />{hasContrib && <><circle className="gauge-track-acoustic" cx="100" cy="100" r="66" /><motion.circle className="gauge-val-acoustic" cx="100" cy="100" r="66" strokeDasharray={circAc} initial={{ strokeDashoffset: circAc }} animate={{ strokeDashoffset: visible ? circAc * (1 - acVal * .83) : circAc }} transition={{ duration: reduced ? 0 : 1.1, delay: .08, ease: [.22, 1, .36, 1] }} /><circle className="gauge-track-ling" cx="100" cy="100" r="57" /><motion.circle className="gauge-val-ling" cx="100" cy="100" r="57" strokeDasharray={circLi} initial={{ strokeDashoffset: circLi }} animate={{ strokeDashoffset: visible ? circLi * (1 - liVal * .83) : circLi }} transition={{ duration: reduced ? 0 : 1.1, delay: .15, ease: [.22, 1, .36, 1] }} /><circle className="gauge-track-ctx" cx="100" cy="100" r="49" /><motion.circle className="gauge-val-ctx" cx="100" cy="100" r="49" strokeDasharray={circCx} initial={{ strokeDashoffset: circCx }} animate={{ strokeDashoffset: visible ? circCx * (1 - cxVal * .83) : circCx }} transition={{ duration: reduced ? 0 : 1.1, delay: .22, ease: [.22, 1, .36, 1] }} /></>}{Array.from({ length: 33 }, (_, i) => <line className="gauge-tick" key={i} x1="100" y1="5" x2="100" y2={i % 4 === 0 ? '10' : '8'} transform={`rotate(${i * 9.2 - 147} 100 100)`} />)}</svg><div className="gauge-readout"><strong>{Math.round(safeValue * 100)}<small>%</small></strong><span>{label}</span></div><span className="gauge-bottom">{hasContrib ? 'MULTI-SIGNAL FUSION' : 'RISK INDEX'}</span>{hasContrib && <div className="gauge-contrib-legend"><span><i className="contrib-dot dot-acoustic" />Acoustic</span><span><i className="contrib-dot dot-ling" />Language</span><span><i className="contrib-dot dot-ctx" />Context</span></div>}</div>
}
export function SignalFusion({ scores, weights, final, source }) {
  const [selected, setSelected] = useState('acoustic')
  const diagram = useRef(null)
  const visible = useInView(diagram)
  const nodes = [{ id: 'acoustic', label: 'Acoustic', icon: 'wave', description: 'Acoustic evidence describes characteristics of the voice signal.' }, { id: 'linguistic', label: 'Linguistic', icon: 'code', description: 'Language analysis looks for pressure, secrecy, and other risk cues.' }, { id: 'context', label: 'Context', icon: 'grid', description: 'Context weights the circumstances and selected analysis profile.' }]
  const node = nodes.find(n => n.id === selected)
  return <div className="fusion-interactive" ref={diagram} style={{ '--signal-play-state': visible ? 'running' : 'paused' }}><div className="fusion-diagram"><div className="fusion-inputs">{nodes.map(n => <button key={n.id} className={`fusion-node ${selected === n.id ? 'active' : ''}`} onClick={() => setSelected(n.id)} aria-pressed={selected === n.id}><Icon name={n.icon} size={18} /><span>{n.label}</span><strong>{percent(scores[n.id])}</strong></button>)}</div><div className="fusion-connectors" aria-hidden="true"><svg viewBox="0 0 200 180" preserveAspectRatio="none"><path d="M0 26C100 26 65 90 200 90M0 90H200M0 154C100 154 65 90 200 90" /><path className={`signal-path signal-${selected}`} d={selected === 'acoustic' ? 'M0 26C100 26 65 90 200 90' : selected === 'context' ? 'M0 154C100 154 65 90 200 90' : 'M0 90H200'} /></svg></div><div className="fusion-output"><Icon name="shield" size={24} /><strong>{percent(final)}</strong><span>Final risk</span><small>{source === 'demo' ? 'DEMO' : 'API RESULT'}</small></div></div><div className="fusion-inspector" aria-live="polite"><span className="eyebrow">{node.label.toUpperCase()} CONTRIBUTION</span><strong>{percent(scores[selected])} <span>× {weights[selected]?.toFixed(2) ?? '—'}</span><Icon name="arrow" size={17} />{Number.isFinite(scores[selected]) && Number.isFinite(weights[selected]) ? `${(scores[selected] * weights[selected] * 100).toFixed(1)} pts` : '—'}</strong><p>{node.description}</p></div></div>
}
