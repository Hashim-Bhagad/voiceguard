import { useEffect, useRef } from 'react'
import { token as css } from '../lib/tokens'

/*
  Press feedback in the site's own material: clicking a control throws a handful of
  square pixels out of the press point and leaves a stepped ring, like one tick of the
  meter. One canvas for the whole app, drawn only while something is in flight.
  Quieter inside the workspace, off for touch-free keyboard presses and reduced motion.
*/

const TARGETS = 'a[href], button:not(:disabled), [role="button"], [role="tab"], [role="option"], [role="menuitem"], [role="checkbox"], [role="radio"], [role="switch"], summary, label[for]'


export default function ClickBurst() {
  const ref = useRef(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    const colors = [css('--amber-500'), css('--amber-600'), css('--paper')]
    let w = 0, h = 0, raf = 0, last = 0
    const bits = [], rings = []

    function size() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = window.innerWidth; h = window.innerHeight
      canvas.width = w * dpr; canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    function frame(now) {
      const dt = Math.min(0.033, (now - last) / 1000)
      last = now
      ctx.clearRect(0, 0, w, h)
      for (let i = bits.length - 1; i >= 0; i--) {
        const b = bits[i]
        b.age += dt
        if (b.age >= b.life) { bits.splice(i, 1); continue }
        b.vx *= 0.9; b.vy = b.vy * 0.9 + 520 * dt
        b.x += b.vx * dt; b.y += b.vy * dt
        const k = 1 - b.age / b.life
        ctx.globalAlpha = k
        ctx.fillStyle = b.color
        const s = Math.max(1, Math.round(b.s * (0.5 + 0.5 * k)))
        // Snap to whole pixels so the squares stay crisp.
        ctx.fillRect(Math.round(b.x - s / 2), Math.round(b.y - s / 2), s, s)
      }
      for (let i = rings.length - 1; i >= 0; i--) {
        const r = rings[i]
        r.age += dt
        if (r.age >= 0.42) { rings.splice(i, 1); continue }
        const p = r.age / 0.42
        const rad = r.from + (r.to - r.from) * (1 - (1 - p) ** 3)
        // A ring of 16 square cells, stepped like the meter.
        ctx.globalAlpha = 0.7 * (1 - p)
        ctx.fillStyle = colors[0]
        for (let k = 0; k < 16; k++) {
          const a = (k / 16) * Math.PI * 2
          ctx.fillRect(Math.round(r.x + Math.cos(a) * rad) - 1.5, Math.round(r.y + Math.sin(a) * rad) - 1.5, 3, 3)
        }
      }
      ctx.globalAlpha = 1
      raf = bits.length || rings.length ? requestAnimationFrame(frame) : 0
    }

    function onDown(e) {
      if (e.button !== 0) return
      const el = e.target instanceof Element ? e.target.closest(TARGETS) : null
      if (!el || el.closest('[data-no-burst]') || el.getAttribute('aria-disabled') === 'true') return
      const quiet = window.location.pathname.startsWith('/dashboard')
      const n = quiet ? 6 : 12
      for (let i = 0; i < n; i++) {
        const a = Math.random() * Math.PI * 2
        const v = (quiet ? 90 : 140) + Math.random() * (quiet ? 120 : 260)
        bits.push({
          x: e.clientX, y: e.clientY,
          vx: Math.cos(a) * v, vy: Math.sin(a) * v - 60,
          s: 3 + Math.round(Math.random() * 3),
          color: colors[i % 5 === 4 ? 2 : i % 3 === 0 ? 1 : 0],
          age: 0, life: 0.38 + Math.random() * 0.3,
        })
      }
      rings.push({ x: e.clientX, y: e.clientY, from: 6, to: quiet ? 20 : 30, age: 0 })
      if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame) }
    }

    size()
    window.addEventListener('resize', size)
    document.addEventListener('pointerdown', onDown, { capture: true, passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', size)
      document.removeEventListener('pointerdown', onDown, { capture: true })
    }
  }, [])

  return <canvas ref={ref} className="pointer-events-none fixed inset-0 z-[90] h-full w-full" aria-hidden="true" />
}
