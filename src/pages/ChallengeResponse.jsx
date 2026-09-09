import { useState } from 'react'
import { useAnalysis } from '../lib/AnalysisContext'
import './Dashboard.css'

function generateCode() {
  return Array.from({ length: 4 }, () => Math.floor(Math.random() * 10)).join(' ')
}

export default function ChallengeResponse() {
  const { data } = useAnalysis()
  const [code] = useState(generateCode) // generated once per page visit, not on every render
  const [status, setStatus] = useState('listening') // listening | verifying | pass | fail

  if (!data) {
    return (
      <div className="dash-page">
        <h1 className="dash-title">Challenge-Response</h1>
        <p className="dash-subtitle">Live verification triggered by elevated risk</p>
        <p className="dash-empty-hint">
          No active call. Go to Live Monitoring and run an analysis first.
        </p>
      </div>
    )
  }

  return (
    <div className="dash-page">
      <h1 className="dash-title">Challenge-Response</h1>
      <p className="dash-subtitle">Live verification triggered by elevated risk</p>

      <div className="dash-card" style={{ textAlign: 'center' }}>
        <h3>Generated Code</h3>
        <div className="dash-challenge-code">{code}</div>

        {status === 'listening' && (
          <span className="dash-status-pill" style={{ justifyContent: 'center' }}>
            <span className="dash-dot-pulse" /> Listening for response…
          </span>
        )}
        {status === 'verifying' && (
          <span className="dash-status-pill" style={{ justifyContent: 'center' }}>
            <span className="dash-dot-pulse" /> Verifying…
          </span>
        )}
        {status === 'pass' && (
          <span className="dash-badge tone-safe" style={{ fontSize: 14 }}>Pass — natural response</span>
        )}
        {status === 'fail' && (
          <span className="dash-badge tone-high" style={{ fontSize: 14 }}>Fail — synthetic response detected</span>
        )}

        <div className="dash-actions dash-actions--challenge">
          <button onClick={() => setStatus('listening')}>Reset</button>
          <button onClick={() => setStatus('verifying')}>Simulate: Verifying</button>
          <button onClick={() => setStatus('pass')}>Simulate: Pass</button>
          <button onClick={() => setStatus('fail')}>Simulate: Fail</button>
        </div>
      </div>
    </div>
  )
}
