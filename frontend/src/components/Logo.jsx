import { Link } from 'react-router-dom'

// The mark is the hero meter in miniature: four pixel columns, the tallest lit amber.
export function Mark({ className = 'size-6' }) {
  const cols = [2, 4, 3, 5]
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      {cols.map((h, c) =>
        Array.from({ length: h }, (_, r) => (
          <rect
            key={`${c}-${r}`}
            x={1 + c * 6}
            y={21 - r * 4}
            width="4"
            height="3"
            rx="0.6"
            fill={c === 3 ? 'var(--accent)' : 'var(--foreground)'}
            opacity={c === 3 ? 1 : 0.35 + r * 0.15}
          />
        )),
      )}
    </svg>
  )
}

export default function Logo({ to = '/', compact = false, className = '' }) {
  return (
    <Link to={to} aria-label="VoiceGuard home" className={`inline-flex items-center gap-2.5 ${className}`}>
      <Mark />
      {!compact && <span className="text-[1rem] font-semibold tracking-[-0.02em] text-foreground">VoiceGuard</span>}
    </Link>
  )
}
