import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import './Navbar.css'


const SCROLL_THRESHOLD = 80


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
  <a href="#how-it-works">How it works</a>
  <Link to="/dashboard">Dashboard</Link>
  <a href="#docs">Docs</a>
  <a className="navbar-cta" href="#demo">
    Request demo
  </a>
</nav>
    </header>
  )
}
