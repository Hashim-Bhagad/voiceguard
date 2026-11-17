import { useEffect, useRef } from 'react'
import { token, toRgb } from '../lib/tokens'

/*
  A pixel trail under the whole landing page: cells along the cursor's path light up
  and cool down along the brand ramp, pale gold where the cursor is, then amber,
  then a deep orange ember as they fade. The same pixel language as the voice meter. It sits behind the
  content (sections are transparent, cards are opaque), runs only while something is
  lit, and stays off for touch screens and reduced motion.
*/
const CELL = 14
const GAP = 3

export default function PixelTrail() {
  const ref = useRef(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    if (!window.matchMedia('(pointer: fine)').matches) return
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    // Heat ramp, resolved once to 32 rgb strings.
    const tok = token, rgb = toRgb
    const amber = rgb(tok('--amber-500')), hot = rgb(tok('--amber-600'))
    const paper = rgb(tok('--paper'))
    const gold = amber.map((v, i) => v + (paper[i] - v) * 0.45)
    // Red means "clone" everywhere else on the page, so the trail stops at orange.
    const ember = hot.map(v => v * 0.78)
    const stops = [[0, ember], [0.3, hot], [0.62, amber], [1, gold]]
    const ramp = Array.from({ length: 32 }, (_, k) => {
      const v = k / 31
      let j = 0
      while (j < stops.length - 2 && v > stops[j + 1][0]) j++
      const [a, ca] = stops[j], [b, cb] = stops[j + 1]
      const f = (v - a) / (b - a || 1)
      return `rgb(${ca.map((x, i) => Math.round(x + (cb[i] - x) * f)).join(',')})`
    })
    let w = 0, h = 0, cols = 0, rows = 0, dpr = 1
    let heat = new Float32Array(0)
    const lit = new Set()
    let last = null, raf = 0

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = window.innerWidth; h = window.innerHeight
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      cols = Math.ceil(w / CELL); rows = Math.ceil(h / CELL)
      heat = new Float32Array(cols * rows); lit.clear()
    }

    function light(x, y, amount) {
      const c = Math.floor(x / CELL), r = Math.floor(y / CELL)
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const cc = c + dx, rr = r + dy
          if (cc < 0 || rr < 0 || cc >= cols || rr >= rows) continue
          const falloff = dx === 0 && dy === 0 ? 1 : (dx && dy ? 0.25 : 0.45)
          const i = rr * cols + cc
          heat[i] = Math.min(1, heat[i] + amount * falloff * (0.6 + Math.random() * 0.4))
          lit.add(i)
        }
      }
    }

    function frame() {
      raf = 0
      ctx.clearRect(0, 0, w, h)
      for (const i of lit) {
        const v = (heat[i] *= 0.92)
        if (v < 0.02) { heat[i] = 0; lit.delete(i); continue }
        ctx.fillStyle = ramp[Math.min(31, Math.round(v * 31))]
        ctx.globalAlpha = 0.12 + v * 0.48
        ctx.fillRect((i % cols) * CELL + GAP / 2, Math.floor(i / cols) * CELL + GAP / 2, CELL - GAP, CELL - GAP)
      }
      ctx.globalAlpha = 1
      if (lit.size) raf = requestAnimationFrame(frame)
    }

    function onMove(e) {
      const p = { x: e.clientX, y: e.clientY }
      if (last) {
        const dist = Math.hypot(p.x - last.x, p.y - last.y)
        const steps = Math.min(24, Math.ceil(dist / (CELL * 0.75)))
        for (let s = 1; s <= steps; s++) light(last.x + ((p.x - last.x) * s) / steps, last.y + ((p.y - last.y) * s) / steps, 0.55)
      } else light(p.x, p.y, 0.55)
      last = p
      if (!raf) raf = requestAnimationFrame(frame)
    }
    const onLeave = () => { last = null }

    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', onMove, { passive: true })
    document.addEventListener('pointerleave', onLeave)
    window.addEventListener('scroll', onLeave, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onMove)
      document.removeEventListener('pointerleave', onLeave)
      window.removeEventListener('scroll', onLeave)
    }
  }, [])

  return <canvas ref={ref} className="pointer-events-none fixed inset-0 z-0 size-full" aria-hidden="true" />
}
