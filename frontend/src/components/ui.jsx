import { motion } from 'motion/react'
import { Link } from 'react-router-dom'

const paths = {
  shield: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z M8 12l3 3 5-6',
  wave: 'M3 10v4m4-7v10m5-14v18m5-14v10m4-7v4',
  grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  alert: 'm12 3 10 18H2L12 3Z M12 9v5m0 3v.1',
  mic: 'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5Z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3m-4 0h8',
  history: 'M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  upload: 'M12 16V3m-5 5 5-5 5 5 M4 15v6h16v-6',
  lock: 'M5 10h14v11H5z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3',
  check: 'm5 12 4 4L19 6',
  transfer: 'M3 7h18m-4-4 4 4-4 4 M21 17H3m4-4-4 4 4 4',
  chevron: 'm9 5 7 7-7 7',
  external: 'M14 3h7v7m0-7L10 14 M10 3H3v18h18v-7',
  search: 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z m5 12 6 6',
  close: 'm5 5 14 14M5 19 19 5',
  code: 'm8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18',
  play: 'm8 4 12 8-12 8V4Z',
}
export function Icon({ name = 'shield', size = 20, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={paths[name] || paths.shield} /></svg>
}
export function Brand({ compact = false }) { return <Link to="/" className="brand" aria-label="VoiceGuard home"><span className="brand-icon"><Icon name="wave" size={22} /></span>{!compact && <>voiceguard<span className="brand-period">.</span></>}</Link> }
export function PageHeading({ eyebrow, title, children, action }) { return <header className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{children && <p>{children}</p>}</div>{action}</header> }
export function Panel({ title, meta, children, className = '' }) { return <section className={`panel ${className}`}>{title && <header className="panel-heading"><h2>{title}</h2>{meta}</header>}{children}</section> }
export function Reveal({ children, className = '', delay = 0 }) { return <motion.div className={className} initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .1 }} transition={{ duration: .5, delay }}>{children}</motion.div> }
export function Waveform({ active = true, className = '' }) { return <div className={`waveform ${active ? 'is-active' : ''} ${className}`} aria-hidden="true">{Array.from({ length: 56 }, (_, i) => <span key={i} style={{ '--height': `${14 + (Math.sin(i * 1.9) ** 2 * 45 + Math.sin(i * .33) ** 2 * 40)}%`, '--delay': `${(i % 11) * -.12}s` }} />)}</div> }
export function PrivacyBadge({ attestation }) { return <span className="privacy-note"><Icon name="lock" size={14} />{attestation?.zero_raw_audio_stored ? 'Service reports no raw audio storage' : 'Audio stays in memory in this browser'}</span> }
export function EmptyState({ title, children, icon = 'wave' }) { return <div className="empty-state"><span className="empty-icon"><Icon name={icon} size={26} /></span><h3>{title}</h3><p>{children}</p></div> }
