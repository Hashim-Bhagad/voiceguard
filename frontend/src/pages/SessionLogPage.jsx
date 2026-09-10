import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAnalysis } from '../lib/AnalysisContext'
import { normalizeAnalysis, request, percent, verdict } from '../lib/analysis'
import { Icon, PageHeading, Panel, EmptyState } from '../components/ui'
export default function SessionLogPage() {
  const { history } = useAnalysis()
  const [remote, setRemote] = useState([])
  const [connection, setConnection] = useState('loading')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [expanded, setExpanded] = useState(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    request('/api/v1/sessions?limit=50', { signal: controller.signal }, 6000).then(rows => {
      if (controller.signal.aborted) return
      if (!Array.isArray(rows)) throw new Error('Invalid session response')
      setRemote(rows.flatMap(row => { try { return [normalizeAnalysis({ ...row, server_ts: row.timestamp }, row.caller || 'Recorded conversation')] } catch { return [] } }))
      setConnection('connected')
    }).catch(() => { if (!controller.signal.aborted) setConnection('offline') })
    return () => controller.abort()
  }, [revision])
  const sessions = useMemo(() => {
    const byId = new Map(remote.map(row => [row.session_id, row]))
    history.forEach(row => byId.set(row.session_id, row))
    return [...byId.values()].sort((a, b) => b.timestamp - a.timestamp)
  }, [remote, history])
  const rows = sessions.filter(row => `${row.name} ${row.session_id} ${row.transcript}`.toLowerCase().includes(query.toLowerCase()) && (filter === 'all' || filter === row.source || filter === verdict(row).tone))
  return <><PageHeading eyebrow="SESSION INTELLIGENCE" title="Every conversation, in context." action={<button className="button ghost compact" disabled={connection === 'loading'} onClick={() => { setConnection('loading'); setRevision(n => n + 1) }}><Icon name="history" size={16} />Refresh</button>}>Review recent results. Expand a session to revisit its evidence.</PageHeading><Panel className="history-panel" title="Conversation history" meta={<span className="badge neutral">{sessions.length} SESSIONS</span>}><div className="history-tools"><label className="search-field"><Icon name="search" size={17} /><input aria-label="Search sessions" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search conversations, transcripts, or session IDs…" /></label><select value={filter} onChange={e => setFilter(e.target.value)} aria-label="Filter sessions"><option value="all">All sessions</option><option value="high">High risk</option><option value="caution">Review needed</option><option value="safe">Low risk</option><option value="demo">Demo sessions</option><option value="live">API sessions</option></select></div><div className="history-connection" role="status"><span className={`status-dot ${connection === 'loading' ? 'pulse' : ''}`} />{connection === 'loading' ? 'Fetching service history…' : connection === 'offline' ? 'Service history unavailable. Showing sessions available in this visit.' : 'Service history loaded. Demo sessions stay in this visit.'}</div>{rows.length ? <div className="history-table-scroll"><table className="history-table"><thead><tr><th>Conversation</th><th>Time</th><th>Source</th><th>Risk</th><th>Verdict</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{rows.map(row => <SessionRows key={row.session_id} row={row} expanded={expanded === row.session_id} toggle={() => setExpanded(expanded === row.session_id ? null : row.session_id)} />)}</tbody></table></div> : <EmptyState icon="history" title={sessions.length ? 'No conversations match.' : 'Your next conversation starts the story.'}>{sessions.length ? 'Try another search or filter.' : 'Run an analysis to add a session here. Prepared demos are always labeled.'}</EmptyState>}<div className="history-bottom"><span>{rows.length} of {sessions.length} sessions</span><Link to="/dashboard">New analysis <Icon name="arrow" size={14} /></Link></div></Panel></>
}
function SessionRows({ row, expanded, toggle }) {
  const tone = verdict(row)
  return <><tr><td><div className="table-conversation"><span className="table-audio-icon"><Icon name="wave" size={18} /></span><span><strong>{row.name}</strong><small>{row.session_id}</small></span></div></td><td className="mono">{new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}<small>{new Date(row.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' })}</small></td><td><span className={`badge ${row.source === 'demo' ? 'demo' : 'neutral'}`}>{row.source === 'demo' ? 'Demo' : 'API'}</span></td><td className={`table-risk tone-${tone.tone}`}>{percent(row.final_risk_score)}</td><td><span className={`badge ${tone.tone}`}>{tone.label}</span></td><td><button className="icon-button" aria-label={`${expanded ? 'Collapse' : 'Expand'} ${row.name}`} aria-expanded={expanded} aria-controls={`detail-${row.session_id}`} onClick={toggle}><Icon name="chevron" className={expanded ? 'rotate-down' : ''} size={17} /></button></td></tr>{expanded && <tr className="session-detail" id={`detail-${row.session_id}`}><td colSpan={6}><div><span className="eyebrow">SESSION EVIDENCE</span><p>{row.transcript || 'No transcript was returned.'}</p><div className="chips">{row.flags.map(flag => <span key={flag}>{flag.replaceAll('_', ' ')}</span>)}</div><div className="session-scores"><span>Acoustic <b>{percent(row.acoustic_risk_score)}</b></span><span>Linguistic <b>{percent(row.linguistic_risk_score)}</b></span><span>Context <b>{percent(row.context_risk)}</b></span></div></div></td></tr>}</>
}
