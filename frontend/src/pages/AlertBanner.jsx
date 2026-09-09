import { useAnalysis } from '../lib/AnalysisContext'
import './Dashboard.css'

function pct(x) {
  return Math.round((x ?? 0) * 100)
}

function verdictFor(risk) {
  if (risk >= 70) return { label: 'High Risk', tone: 'high' }
  if (risk >= 40) return { label: 'Caution', tone: 'caution' }
  return { label: 'Safe', tone: 'safe' }
}

export default function AlertBanner() {
  const { data } = useAnalysis()

  if (!data) {
    return (
      <div className="dash-page">
        <h1 className="dash-title">Alert</h1>
        <p className="dash-subtitle">Fired when the fused risk score crosses a threshold</p>
        <p className="dash-empty-hint">
          No active call. Go to Live Monitoring and run an analysis first.
        </p>
      </div>
    )
  }

  const finalRisk = pct(data.final_risk_score)
  const verdict = verdictFor(finalRisk)

  return (
    <div className="dash-page">
      <h1 className="dash-title">Alert</h1>
      <p className="dash-subtitle">Fired when the fused risk score crosses a threshold</p>

      <div
        className="dash-card"
        style={{
          borderColor:
            verdict.tone === 'high' ? 'rgba(255,77,77,0.4)' :
            verdict.tone === 'caution' ? 'rgba(245,166,35,0.4)' :
            'rgba(46,204,113,0.4)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span className={`dash-badge tone-${verdict.tone}`} style={{ fontSize: 16, padding: '8px 16px' }}>
            {verdict.label} — {finalRisk}%
          </span>
        </div>

        <h3>Transcript</h3>
        <div className="dash-transcript" tabIndex={0} role="region" aria-label="Flagged transcript">{data.transcript}</div>

        <h3 style={{ marginTop: 20 }}>Flags</h3>
        <div className="dash-flag-list">
          {data.flags.map((f) => (
            <span className="dash-flag" key={f}>{f.replaceAll('_', ' ')}</span>
          ))}
        </div>
      </div>
    </div>
  )
}
