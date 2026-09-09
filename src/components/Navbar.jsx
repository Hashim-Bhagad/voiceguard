import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import './Navbar.css'


const SCROLL_THRESHOLD = 80


export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [showDemo, setShowDemo] = useState(false)

  useEffect(() => {
    function handleScroll() {
      const next = window.scrollY > SCROLL_THRESHOLD
      setScrolled((prev) => (prev === next ? prev : next))
    }

    handleScroll()
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <header className={`navbar${scrolled ? ' navbar--scrolled' : ''}`}>
      <a className="navbar-wordmark" href="#top">
        VOICEGUARD
      </a>

      <nav className="navbar-links">
  <a href="#how-it-works">How it works</a>
  <Link to="/dashboard">Dashboard</Link>
  <a href="#docs">Docs</a>
  <button className="navbar-cta" onClick={() => setShowDemo(true)}>
  Request demo
</button>
  
</nav>
      {showDemo && (
        <div
          onClick={() => setShowDemo(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 50,
          }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => {
              e.preventDefault()
              setShowDemo(false)
            }}
            style={{
              background: '#0D131C',
              border: '1px solid #1e293b',
              padding: '24px',
              width: '100%',
              maxWidth: '360px',
            }}
          >
            <h3 style={{ color: '#f1f5f9', marginBottom: '16px' }}>Request a demo</h3>
            <input
              required
              placeholder="Name"
              style={{
                width: '100%',
                marginBottom: '12px',
                background: 'transparent',
                border: '1px solid #334155',
                padding: '8px 12px',
                fontSize: '14px',
                color: '#e2e8f0',
              }}
            />
            <input
              required
              type="email"
              placeholder="Work email"
              style={{
                width: '100%',
                marginBottom: '16px',
                background: 'transparent',
                border: '1px solid #334155',
                padding: '8px 12px',
                fontSize: '14px',
                color: '#e2e8f0',
              }}
            />
            <button
              type="submit"
              style={{
                width: '100%',
                background: '#22d3ee',
                color: '#000',
                padding: '10px',
                fontSize: '14px',
                border: 'none',
              }}
            >
              Submit
            </button>
          </form>
        </div>
      )}
    </header>
  )
}
