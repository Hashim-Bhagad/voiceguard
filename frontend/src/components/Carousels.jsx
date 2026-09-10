import { useRef, useState, useEffect } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Icon, Waveform } from './ui'
import { SCENARIOS, percent } from '../lib/analysis'

export function Carousel({ label, items, className = '' }) {
  const [index, setIndex] = useState(0)
  const rail = useRef(null)
  const reduce = useReducedMotion()
  function go(next) {
    const clamped = Math.max(0, Math.min(items.length - 1, next))
    rail.current?.scrollTo({ left: clamped * rail.current.clientWidth, behavior: reduce ? 'instant' : 'smooth' })
  }
  return <section className={`carousel ${className}`} aria-roledescription="carousel" aria-label={label}><div className="carousel-rail" ref={rail} tabIndex={0} onKeyDown={e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); go(index + (e.key === 'ArrowRight' ? 1 : -1)) } }} onScroll={e => { const el = e.currentTarget; setIndex(Math.round(el.scrollLeft / el.clientWidth)) }}>{items.map((item, i) => <div className="carousel-slide" key={item.id || i} role="group" aria-roledescription="slide" aria-label={`${i + 1} of ${items.length}`} inert={index !== i}>{item.content}</div>)}</div><div className="carousel-controls"><span className="carousel-position mono">{String(index + 1).padStart(2, '0')}<span> / {String(items.length).padStart(2, '0')}</span></span><div className="carousel-dots">{items.map((item, i) => <button key={item.id || i} className={index === i ? 'active' : ''} aria-label={`Go to ${label} slide ${i + 1}`} aria-current={index === i ? 'true' : undefined} onClick={() => go(i)} />)}</div><div className="carousel-arrows"><button className="icon-button" aria-label={`Previous ${label}`} onClick={() => go(index - 1)} disabled={index === 0}><Icon name="arrow" className="reverse" size={17} /></button><button className="icon-button" aria-label={`Next ${label}`} onClick={() => go(index + 1)} disabled={index === items.length - 1}><Icon name="arrow" size={17} /></button></div></div></section>
}
export function ScenarioCarousel({ onSelect, disabled }) {
  return <Carousel label="Demo scenarios" className="scenario-carousel" items={SCENARIOS.map((s, i) => ({ id: s.id, content: <div className={`scenario-stage scenario-${i}`}><div className="scenario-stage-copy"><div className="scenario-kicker"><span className="badge demo">PREPARED DEMO</span><span>{s.language}</span></div><h3>{s.name}</h3><button className="button primary compact" disabled={disabled} onClick={() => onSelect(s.id)}>Analyze this scenario <Icon name="arrow" size={16} /></button></div><div className="scenario-stage-visual"><span className="scenario-watermark"><Icon name={s.icon} size={100} /></span><blockquote>“{s.transcript}”</blockquote><div className="scenario-preview-signals"><span>Acoustic <b>{percent(s.scores[0])}</b></span><span>Language <b>{percent(s.scores[1])}</b></span><span>Context <b>{percent(s.scores[2])}</b></span></div></div></div> }))} />
}
export function EvidenceCarousel({ data }) {
  const items = [
    { id: 'pitch', name: 'Pitch variation', title: 'The details inside the voice.', metric: Number.isFinite(data.explainability?.jitter_pct) ? `${data.explainability.jitter_pct.toFixed(2)}%` : 'Unavailable', label: 'PITCH MICRO-JITTER', description: 'Small changes between vocal cycles add context to acoustic analysis. Interpret this metric alongside the other signals.', kind: 'pitch' },
    { id: 'spectral', name: 'Spectral evidence', title: 'A closer view of the spectrum.', metric: Number.isFinite(data.explainability?.spectral_discontinuity) ? data.explainability.spectral_discontinuity.toFixed(2) : 'Unavailable', label: 'DISCONTINUITY SCORE', description: 'The service’s spectral discontinuity score describes a signal feature. It is not a frequency measurement or proof of synthesis.', kind: 'spectral' },
    { id: 'language', name: 'Language cues', title: 'Intent leaves a different trace.', metric: String(data.flags.length), label: 'LANGUAGE & RISK FLAGS', description: data.flags.length ? data.flags.map(f => f.replaceAll('_', ' ')).join(' · ') : 'No risk flags were returned. Always use your established verification process.', kind: 'language' },
  ]
  return <Carousel label="Forensic evidence" items={items.map(item => ({ id: item.id, content: <div className="evidence-slide"><div className={`evidence-graphic ${item.kind}`} aria-hidden="true">{item.kind === 'language' ? <div className="language-nodes"><span>VOICE</span><i /><span>INTENT</span><i /><span>CONTEXT</span></div> : <><div className="graphic-grid" /><Waveform active /><span className="graphic-caption">{data.source === 'demo' ? 'DEMO SIGNAL VISUALIZATION' : 'ILLUSTRATIVE SIGNAL VIEW'}</span></>}</div><div className="evidence-copy"><span className="eyebrow">{item.label}</span><div className="evidence-metric">{item.metric}</div><h3>{item.title}</h3><p>{item.description}</p></div></div> }))} />
}
export function ProductShowcase() {
  const [active, setActive] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const reduce = useReducedMotion()
  const tabs = [
    { id: 'analyze', title: 'Analyze', label: '01 / Analyze' },
    { id: 'understand', title: 'Understand', label: '02 / Understand' },
    { id: 'verify', title: 'Verify', label: '03 / Verify' }
  ]

  useEffect(() => {
    if (isPaused) return
    const timer = setInterval(() => {
      setActive(prev => (prev + 1) % tabs.length)
    }, 3600)
    return () => clearInterval(timer)
  }, [isPaused, tabs.length])

  return <div className="product-showcase" onMouseEnter={() => setIsPaused(true)} onMouseLeave={() => setIsPaused(false)}><div className="showcase-tabs" role="tablist" aria-label="Product workflow">{tabs.map((tab, i) => <button key={tab.id} id={`showcase-tab-${i}`} aria-controls="showcase-panel" role="tab" aria-selected={active === i} tabIndex={active === i ? 0 : -1} onKeyDown={e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); const next = (i + (e.key === 'ArrowRight' ? 1 : 2)) % tabs.length; setActive(next); document.getElementById(`showcase-tab-${next}`)?.focus() } }} onClick={() => setActive(i)}>{active === i && <><motion.span className="showcase-tab-active" layoutId="showcase-tab" transition={{ type: 'spring', stiffness: 350, damping: 28 }} />{!reduce && <motion.span key={`prog-${active}-${isPaused}`} className="showcase-tab-progress" initial={{ scaleX: 0 }} animate={{ scaleX: isPaused ? 0 : 1 }} transition={{ duration: 3.6, ease: 'linear' }} />}</>}<span>{tab.label}</span></button>)}</div><div role="tabpanel" id="showcase-panel" aria-labelledby={`showcase-tab-${active}`} className="showcase-body"><AnimatePresence mode="wait"><motion.div key={active} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: .2 }}>{active === 0 ? <><div className="showcase-heading"><Icon name="wave" /><span>A CONVERSATION, DECODED</span><span className="badge demo">DEMO</span></div><Waveform active className="showcase-waveform" /><blockquote>“Turant transfer kar do. Kisi ko mat batana.”</blockquote><div className="chips"><span>Urgency</span><span>Secrecy</span><span>Authority</span></div></> : active === 1 ? <><div className="showcase-heading"><Icon name="search" /><span>THREE SIGNALS. ONE VIEW.</span><span className="badge demo">DEMO</span></div><div className="showcase-fusion">{[['76%', 'Acoustic', '55% weight'], ['88%', 'Language', '25% weight'], ['40%', 'Context', '20% weight']].map(([v, t, w]) => <div key={t}><strong>{v}</strong><span>{t}</span><small>{w}</small></div>)}<div><strong>72%</strong><span>Combined risk</span><small>Rounded weighted result</small></div></div></> : <><div className="showcase-heading"><Icon name="shield" /><span>A FRESH CHALLENGE</span><span className="badge demo">DEMO</span></div><div className="showcase-challenge"><div className="mini-digits"><span>4</span><span>7</span><span>2</span><span>9</span></div><p>Ask the caller to repeat the numbers.</p><span className="privacy-note"><Icon name="mic" size={16} />Compare spoken tokens and acoustic evidence.</span></div></>}</motion.div></AnimatePresence></div></div>
}
