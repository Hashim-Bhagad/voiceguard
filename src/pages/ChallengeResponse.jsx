import { useState } from 'react'
import { useAnalysis } from '../lib/useAnalysis'
import './Dashboard.css'

const CHALLENGE_CODE = '7 4 1 9'

export default function ChallengeResponse() {
  const a = useAnalysis()
  const [status, setStatus] = useState('listening') // listening | verifying | pass | fail

  return (
    <div className="dash-page">
      <h1 className="dash-title">Challenge-Response</h1>
      <p className="dash-subtitle">Live verification triggered by elevated risk</p>

      <div className="dash-card" style={{ textAlign: 'center' }}>
        <h3>Generated Code</h3>
        <div className="dash-challenge-code">{CHALLENGE_CODE}</div>

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

        <div style={{ marginTop: 30, display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button onClick={() => setStatus('listening')}>Reset</button>
          <button onClick={() => setStatus('verifying')}>Simulate: Verifying</button>
          <button onClick={() => setStatus('pass')}>Simulate: Pass</button>
          <button onClick={() => setStatus('fail')}>Simulate: Fail</button>
        </div>
      </div>
    </div>
  )
}