import { useAnalysis } from '../lib/AnalysisContext'
import AudioInput from '../components/AudioInput'
import './Dashboard.css'

function pct(x) {
  return Math.round((x ?? 0) * 100)
}

function verdictFor(risk) {
  if (risk >= 70) return { label: 'High Risk', tone: 'high' }
  if (risk >= 40) return { label: 'Caution', tone: 'caution' }
  return { label: 'Safe', tone: 'safe' }
}

export default function LiveMonitoring() {
  const { status, data } = useAnalysis()

  return (
    <div className="dash-page">
      <h1 className="dash-title">Live Monitoring</h1>
      <p className="dash-subtitle">Active call — analysis running in real time</p>

      <AudioInput />

      {status === 'idle' && (
        <p className="dash-empty-hint">
          Upload a recording, record from the mic, or use the sample call above to see live analysis.
        </p>
      )}

      {status === 'error' && (
        <p className="dash-empty-hint dash-empty-hint--error">
          Analysis failed. Try again, or use the sample call.
        </p>
      )}

      {data && <LiveMonitoringResults data={data} />}
    </div>
  )
}

// Split out so the JSX below is only ever rendered once `data` actually
// exists — no more optional chaining or `?? 0` fallbacks scattered through
// every score row just to survive a null render.
function LiveMonitoringResults({ data }) {
  const finalRisk = pct(data.final_risk_score)
  const verdict = verdictFor(finalRisk)

  return (
    <div className="dash-grid">
      <div className="dash-card">
        <h3>Waveform</h3>
        <div className="dash-waveform">
          {Array.from({ length: 32 }).map((_, i) => (
            <span key={i} style={{ animationDelay: `${(i % 8) * 0.08}s` }} />
          ))}
        </div>

        <h3>Live Transcript</h3>
        <div className="dash-transcript" tabIndex={0} role="region" aria-label="Live transcript">{data.transcript}</div>

        <div className="dash-flag-list">
          {data.flags.map((f) => (
            <span className="dash-flag" key={f}>{f.replaceAll('_', ' ')}</span>
          ))}
        </div>
      </div>

      <div className="dash-card">
        <h3>Risk Breakdown</h3>

        <div className="dash-score-row">
          <span>Acoustic</span>
          <span className="dash-score-track">
            <span
              className={`dash-score-fill tone-${verdictFor(pct(data.acoustic_risk_score)).tone}`}
              style={{ width: `${pct(data.acoustic_risk_score)}%` }}
            />
          </span>
          <span>{pct(data.acoustic_risk_score)}%</span>
        </div>

        <div className="dash-score-row">
          <span>Linguistic</span>
          <span className="dash-score-track">
            <span
              className={`dash-score-fill tone-${verdictFor(pct(data.linguistic_risk_score)).tone}`}
              style={{ width: `${pct(data.linguistic_risk_score)}%` }}
            />
          </span>
          <span>{pct(data.linguistic_risk_score)}%</span>
        </div>

        <div className="dash-score-row">
          <span>Fused</span>
          <span className="dash-score-track">
            <span
              className={`dash-score-fill tone-${verdict.tone}`}
              style={{ width: `${finalRisk}%` }}
            />
          </span>
          <span>{finalRisk}%</span>
        </div>

        <span className={`dash-badge tone-${verdict.tone}`}>{verdict.label}</span>

        <h3 style={{ marginTop: 24 }}>Challenge Status</h3>
        <span className="dash-status-pill">
          <span className="dash-dot-pulse" />
          {data.challenge_triggered ? 'Triggered' : 'Not triggered'}
        </span>
      </div>
    </div>
  )
}
