import { useAnalysis } from '../lib/AnalysisContext'
import './Dashboard.css'

const MOCK_HISTORY = [
  { time: '1m ago', caller: '+1 (415) 55•-••12', risk: 6 },
  { time: '4m ago', caller: '+91 98••• •••47', risk: 91 },
  { time: '9m ago', caller: '+44 7•••-••••23', risk: 18 },
  { time: '22m ago', caller: '+1 (212) 55•-••88', risk: 44 },
  { time: '1h ago', caller: '+91 98••• •••12', risk: 76 },
  { time: '2h ago', caller: '+61 4•• •••091', risk: 12 },
  { time: '3h ago', caller: '+1 (312) 55•-••34', risk: 68 },
]

function verdictFor(risk) {
  if (risk >= 70) return { label: 'High Risk', tone: 'high' }
  if (risk >= 40) return { label: 'Caution', tone: 'caution' }
  return { label: 'Safe', tone: 'safe' }
}

export default function SessionLogPage() {
  const { data } = useAnalysis()

  // Only prepend a "current session" row once a real analysis has actually
  // run — otherwise every visitor sees a fake 0% "Current session" entry
  // sitting at the top before they've uploaded or recorded anything.
  const rows = data
    ? [
        { time: 'Just now', caller: 'Current session', risk: Math.round(data.final_risk_score * 100) },
        ...MOCK_HISTORY,
      ]
    : MOCK_HISTORY

  return (
    <div className="dash-page">
      <h1 className="dash-title">Session Log</h1>
      <p className="dash-subtitle">Full call history</p>

      <div className="dash-card">
        <table className="dash-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Caller</th>
              <th>Risk</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const v = verdictFor(row.risk)
              return (
                <tr key={row.caller + row.time}>
                  <td>{row.time}</td>
                  <td>{row.caller}</td>
                  <td>{row.risk}%</td>
                  <td><span className={`dash-badge tone-${v.tone}`}>{v.label}</span></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}