import { useEffect } from 'react'
import Lenis from 'lenis'

// Smooth scrolling on the landing page only (never inside the workspace). Lenis
// keeps native scrolling, so motion's useScroll, whileInView and keyboard scrolling
// keep working. It runs its own rAF; nothing else needs its ticker.
export default function useLenis() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const lenis = new Lenis({ duration: 1.1, easing: t => 1 - Math.pow(1 - t, 4), smoothWheel: true, autoRaf: true })
    // In-page anchors (#demo, the skip link) ease like the wheel does, and keyboard
    // focus follows them, as it would with a native jump.
    const onClick = e => {
      const a = e.target.closest('a[href^="#"]')
      if (!a) return
      const el = document.querySelector(a.getAttribute('href'))
      if (!el) return
      e.preventDefault()
      lenis.scrollTo(el, { offset: -72 })
      history.replaceState(null, '', a.getAttribute('href'))
      if (!el.hasAttribute('tabindex') && !el.matches('a, button, input, select, textarea')) el.setAttribute('tabindex', '-1')
      el.focus({ preventScroll: true })
    }
    document.addEventListener('click', onClick)
    return () => {
      document.removeEventListener('click', onClick)
      lenis.destroy()
    }
  }, [])
}
