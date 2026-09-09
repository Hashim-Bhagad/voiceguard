import { useState } from 'react'
import './Footer.css'

const MARQUEE_REPEAT = 6

const SOCIALS = [
  {
    name: 'Instagram',
    href: 'https://instagram.com/voiceguard',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4.2" />
        <circle cx="17.4" cy="6.6" r="0.9" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    name: 'X',
    href: 'https://x.com/voiceguard',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M4 4l16 16M20 4L4 20" />
      </svg>
    ),
  },
  {
    name: 'LinkedIn',
    href: 'https://linkedin.com/company/voiceguard',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="3" y="3" width="18" height="18" rx="3" />
        <line x1="7.5" y1="10" x2="7.5" y2="17" />
        <circle cx="7.5" cy="6.6" r="0.9" fill="currentColor" stroke="none" />
        <path d="M11.5 17v-4.2c0-1.6 1-2.3 2.1-2.3 1.2 0 1.9.8 1.9 2.3V17" />
      </svg>
    ),
  },
]

function MarqueeSet() {
  return (
    <span className="footer-marquee-set">
      {Array.from({ length: MARQUEE_REPEAT }).map((_, i) => (
        <span className="footer-marquee-word" key={i}>
          VOICEGUARD
        </span>
      ))}
    </span>
  )
}

export default function Footer() {
  const [showDemo, setShowDemo] = useState(false)

  return (
    <footer className="site-footer" id="demo">
      <div className="footer-cta">
        <div className="footer-marquee" aria-hidden="true">
          <div className="footer-marquee-track">
            <MarqueeSet />
            <MarqueeSet />
          </div>
        </div>

        <div className="footer-cta-content">
          <h2 className="footer-cta-heading">
            Watch VoiceGuard catch a clone in real time.
          </h2>
          <button
            type="button"
            className="footer-cta-button"
            onClick={() => setShowDemo(true)}
          >
            Request a demo
          </button>
        </div>
      </div>

      <div className="footer-base">
        <div className="footer-identity">
          <span className="footer-wordmark">VOICEGUARD</span>
          <a className="footer-contact" href="mailto:hello@voiceguard.ai">
            hello@voiceguard.ai
          </a>
        </div>

        <div className="footer-social" aria-label="Follow VoiceGuard">
          {SOCIALS.map((s) => (
            <a
              key={s.name}
              href={s.href}
              target="_blank"
              rel="noreferrer"
              aria-label={s.name}
              title={s.name}
            >
              {s.icon}
            </a>
          ))}
        </div>

        <span className="footer-fine-print">© 2026 VoiceGuard.</span>
      </div>

      {showDemo && (
        <div
          className="footer-modal-backdrop"
          onClick={() => setShowDemo(false)}
        >
          <form
            className="footer-modal"
            onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => {
              e.preventDefault()
              setShowDemo(false)
            }}
          >
            <h3>Request a demo</h3>
            <input required placeholder="Name" autoComplete="name" />
            <input
              required
              type="email"
              placeholder="Work email"
              autoComplete="email"
            />
            <button type="submit">Submit</button>
          </form>
        </div>
      )}
    </footer>
  )
}
