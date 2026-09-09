export default function DocsSection() {
  return (
    <section
      id="docs"
      style={{
        border: '1px solid #1e293b',
        padding: '24px',
        fontFamily: 'monospace',
        fontSize: '14px',
        color: '#cbd5e1',
        margin: '80px auto',
        maxWidth: '600px',
      }}
    >
      <div style={{ color: '#22d3ee', marginBottom: '8px' }}>
        POST /analyze → response shape
      </div>
      <pre>{`{
  acoustic_risk_score: number,   // 0–1
  linguistic_risk_score: number, // 0–1
  final_risk_score: number,      // 0–1, fused
  transcript: string,
  flags: string[],
  challenge_triggered: boolean
}`}</pre>
    </section>
  )
}