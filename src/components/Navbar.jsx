import { useEffect, useState } from 'react'
import './Navbar.css'

const SCROLL_THRESHOLD = 80

const LINKS = ['How it works', 'Dashboard', 'Docs']

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)

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
        {LINKS.map((label) => (
          <a key={label} href="#">
            {label}
          </a>
        ))}
        <a className="navbar-cta" href="#demo">
          Request demo
        </a>
      </nav>
    </header>
  )
}
