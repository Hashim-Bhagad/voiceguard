import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AlertDialog, Button, Chip, SearchField, Table, ToggleButton, ToggleButtonGroup } from '@heroui/react'
import { ArrowRight, RefreshCw, Trash2 } from 'lucide-react'
import { useAnalysis } from '@/lib/AnalysisContext'
import { normalizeAnalysis, percent, request, verdict } from '@/lib/analysis'
import { ButtonLink, PageHeader, SourceChip } from './components/ui'
import { TONES } from './tones'

const FILTERS = [
  ['all', 'All'],
  ['high', 'High risk'],
  ['caution', 'Review'],
  ['safe', 'Low risk'],
  ['demo', 'Demos'],
  ['live', 'Live'],
]
const URL_ALIAS = { review: 'caution', low: 'safe' }

const time = ts => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
const day = ts => new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' })

function Detail({ row, onOpen }) {
  if (!row) return null
  const state = verdict(row)
  const tone = TONES[state.tone] || TONES.neutral
  const flags = Array.isArray(row.flags) ? row.flags : []
  return (
    <section aria-label={`Details for ${row.name}`} className="flex flex-col gap-6 rounded-2xl border border-border bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            <Chip size="sm" color={tone.color} variant="soft"><tone.Icon aria-hidden className="size-3.5" /><Chip.Label>{state.label}</Chip.Label></Chip>
            <SourceChip source={row.source} />
          </div>
          <h2 className="text-lg font-semibold tracking-[-0.015em]">{row.name}</h2>
          <span className="font-mono text-xs text-muted">{row.session_id} · {day(row.timestamp)} {time(row.timestamp)}</span>
        </div>
        <span className={`font-pixel text-5xl leading-none tabular ${tone.text}`}>{percent(row.final_risk_score)}</span>
      </div>
      <blockquote className="text-[0.975rem] leading-relaxed text-foreground">{row.transcript ? `“${row.transcript}”` : 'No transcript was returned.'}</blockquote>
      {flags.length > 0 && (
        <div className="flex flex-wrap gap-2">{flags.map(f => <Chip key={f} size="sm" color="warning" variant="soft"><Chip.Label>{f.replaceAll('_', ' ')}</Chip.Label></Chip>)}</div>
      )}
      <dl className="grid grid-cols-3 gap-4">
        {[['Voice spoof score', row.acoustic_risk_score], ['Linguistic', row.linguistic_risk_score], ['Context', row.context_risk]].map(([label, v]) => (
          <div key={label} className="flex flex-col gap-1"><dt className="text-xs text-muted">{label}</dt><dd className="font-mono text-lg tabular">{percent(v)}</dd></div>
        ))}
      </dl>
      <div><Button variant="secondary" onPress={() => onOpen(row)}>Open in Analyze <ArrowRight aria-hidden className="size-4" /></Button></div>
    </section>
  )
}

export default function History() {
  const { history, selectSession, clearHistory } = useAnalysis()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const filterParam = params.get('filter') || 'all'
  const filter = URL_ALIAS[filterParam] || filterParam
  const [query, setQuery] = useState('')
  const [remote, setRemote] = useState([])
  const [connection, setConnection] = useState('loading')
  const [revision, setRevision] = useState(0)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    request('/api/v1/sessions?limit=50', { signal: controller.signal }, 8000).then(rows => {
      if (controller.signal.aborted) return
      if (!Array.isArray(rows)) throw new Error('Invalid session response')
      setRemote(rows.flatMap(row => { try { return [normalizeAnalysis({ ...row, server_ts: row.timestamp }, row.caller || 'Recorded call')] } catch { return [] } }))
      setConnection('connected')
    }).catch(() => { if (!controller.signal.aborted) setConnection('offline') })
    return () => controller.abort()
  }, [revision])

  const sessions = useMemo(() => {
    const byId = new Map(remote.map(r => [r.session_id, r]))
    history.forEach(r => byId.set(r.session_id, r))
    return [...byId.values()].sort((a, b) => b.timestamp - a.timestamp)
  }, [remote, history])

  const rows = sessions.filter(r =>
    `${r.name} ${r.session_id} ${r.transcript}`.toLowerCase().includes(query.toLowerCase()) &&
    (filter === 'all' || filter === r.source || filter === verdict(r).tone))
  const current = rows.find(r => r.session_id === selected) || null

  function setFilter(next) {
    const p = new URLSearchParams(params)
    if (next === 'all') p.delete('filter'); else p.set('filter', next)
    setParams(p, { replace: true })
  }
  function open(row) { selectSession(row); navigate('/dashboard') }

  return (
    <div className="flex flex-col gap-12">
      <PageHeader
        title="History"
        action={<Button size="sm" variant="ghost" isDisabled={connection === 'loading'} onPress={() => { setConnection('loading'); setRevision(n => n + 1) }}><RefreshCw aria-hidden className="size-4" />Refresh</Button>}
      >
        Every call you have analyzed, newest first. Pick one to see its evidence again.
      </PageHeader>

      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <SearchField aria-label="Search calls" value={query} onChange={setQuery} className="w-full lg:max-w-sm">
            <SearchField.Group>
              <SearchField.SearchIcon />
              <SearchField.Input placeholder="Search names, transcripts or session IDs" />
              <SearchField.ClearButton />
            </SearchField.Group>
          </SearchField>
          <div className="-mx-1 overflow-x-auto px-1">
            <ToggleButtonGroup aria-label="Filter calls" selectionMode="single" disallowEmptySelection selectedKeys={new Set([filter])} onSelectionChange={keys => setFilter(String([...keys][0] || 'all'))}>
              {FILTERS.map(([id, label], i) => (
                <ToggleButton key={id} id={id} size="sm">{i > 0 && <ToggleButtonGroup.Separator />}{label}</ToggleButton>
              ))}
            </ToggleButtonGroup>
          </div>
        </div>

        <p role="status" className="flex items-center gap-2 text-xs text-muted">
          <span aria-hidden className={`size-1.5 rounded-full ${connection === 'connected' ? 'bg-success' : connection === 'offline' ? 'bg-warning' : 'animate-pulse bg-muted'}`} />
          {connection === 'loading' ? 'Fetching history from the service' : connection === 'offline' ? 'Service history unavailable. Showing calls from this browser.' : 'Service history loaded. Demo calls stay in this browser.'}
        </p>

        {rows.length ? (
          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
            <Table>
              <Table.ScrollContainer>
                <Table.Content
                  aria-label="Analyzed calls"
                  className="min-w-[560px]"
                  selectionMode="single"
                  selectionBehavior="replace"
                  selectedKeys={selected ? new Set([selected]) : new Set()}
                  onSelectionChange={keys => setSelected([...keys][0] ?? null)}
                >
                  <Table.Header>
                    <Table.Column isRowHeader>Call</Table.Column>
                    <Table.Column>When</Table.Column>
                    <Table.Column>Source</Table.Column>
                    <Table.Column>Risk</Table.Column>
                    <Table.Column>Verdict</Table.Column>
                  </Table.Header>
                  <Table.Body>
                    {rows.map(r => {
                      const state = verdict(r)
                      const tone = TONES[state.tone] || TONES.neutral
                      return (
                        <Table.Row key={r.session_id} id={r.session_id} textValue={r.name}>
                          <Table.Cell>
                            <span className="flex flex-col">
                              <span className="font-medium text-foreground">{r.name}</span>
                              <span className="font-mono text-[0.7rem] text-muted">{r.session_id}</span>
                            </span>
                          </Table.Cell>
                          <Table.Cell><span className="font-mono text-sm tabular">{time(r.timestamp)}</span> <span className="text-xs text-muted">{day(r.timestamp)}</span></Table.Cell>
                          <Table.Cell><SourceChip source={r.source} /></Table.Cell>
                          <Table.Cell><span className={`font-mono tabular ${tone.text}`}>{percent(r.final_risk_score)}</span></Table.Cell>
                          <Table.Cell><Chip size="sm" color={tone.color} variant="soft"><Chip.Label>{state.label}</Chip.Label></Chip></Table.Cell>
                        </Table.Row>
                      )
                    })}
                  </Table.Body>
                </Table.Content>
              </Table.ScrollContainer>
            </Table>
            {current ? <Detail row={current} onOpen={open} /> : (
              <div className="hidden rounded-2xl border border-dashed border-border p-7 text-sm text-muted xl:flex xl:items-center xl:justify-center">
                Select a call to see its transcript and scores.
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-start gap-4 rounded-2xl border border-dashed border-border p-8">
            <h2 className="text-base font-medium">{sessions.length ? 'No calls match.' : 'No calls yet.'}</h2>
            <p className="text-sm text-muted">{sessions.length ? 'Try another search or filter.' : 'Analyze a sample call or your own recording and it will appear here.'}</p>
            {!sessions.length && <ButtonLink to="/dashboard" variant="primary">Analyze a call</ButtonLink>}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
          <span>{rows.length} of {sessions.length} {sessions.length === 1 ? 'call' : 'calls'}</span>
          {history.length > 0 && (
            <AlertDialog>
              <Button size="sm" variant="ghost"><Trash2 aria-hidden className="size-3.5" />Clear this browser's history</Button>
              <AlertDialog.Backdrop>
                <AlertDialog.Container>
                  <AlertDialog.Dialog className="sm:max-w-[400px]">
                    <AlertDialog.Header>
                      <AlertDialog.Icon status="danger" />
                      <AlertDialog.Heading>Clear {history.length} saved calls?</AlertDialog.Heading>
                    </AlertDialog.Header>
                    <AlertDialog.Body><p>This removes the calls saved in this browser. Sessions stored by the service are not affected.</p></AlertDialog.Body>
                    <AlertDialog.Footer>
                      <Button slot="close" variant="tertiary">Cancel</Button>
                      <Button slot="close" variant="danger" onPress={() => { clearHistory(); setSelected(null) }}>Clear history</Button>
                    </AlertDialog.Footer>
                  </AlertDialog.Dialog>
                </AlertDialog.Container>
              </AlertDialog.Backdrop>
            </AlertDialog>
          )}
        </div>
      </div>
    </div>
  )
}
