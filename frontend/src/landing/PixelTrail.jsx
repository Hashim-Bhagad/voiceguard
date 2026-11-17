import { useEffect, useRef } from 'react'
import { token, toRgb } from '../lib/tokens'
import { INTERACTIVE, isTouch, prefersReduced } from '../lib/touch'

/*
  A pixel field under the whole landing page, in the same pixel language as the
  voice meter. Cells light up and cool down along the brand ramp: pale gold where
  the input is, then amber, then a deep orange ember as they fade.

  Desktop: cells follow the cursor.
  Touch: cells follow the thumb, including while it drags the page, and a tap on
  empty space sends out a sonar ping, two stepped rings of cells that spread from
  the finger like a voice leaving a speaker.

  It sits behind the content (sections are transparent, cards are opaque), runs only
  while something is lit, and stays off for reduced motion.
*/
const CELL = 14
const GAP = 3
const PING_LIFE = 1.05
const PING_SPEED = 560 // px per second at the start, eased out

export default function PixelTrail() {
  const ref = useRef(null)

  useEffect(() => {
    if (prefersReduced()) return
    const fine = window.matchMedia('(pointer: fine)').matches
    const touch = isTouch()
    if (!fine && !touch) return
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    // Heat ramp, resolved once to 32 rgb strings.
    const amber = toRgb(token('--amber-500')), hot = toRgb(token('--amber-600'))
    const paper = toRgb(token('--paper'))
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
    // Per-cell cooling: trail cells linger, ping cells cool fast so the ring stays a ring.
    let rate = new Float32Array(0)
    const lit = new Set()
    const pings = []
    let last = null, raf = 0, prev = 0

    function resize() {
      // Phones resize when the address bar slides; only rebuild when the grid changes.
      const nw = window.innerWidth, nh = window.innerHeight
      if (touch && nw === w && Math.abs(nh - h) < CELL * 6 && heat.length) return
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = nw; h = touch ? Math.max(nh, h) : nh
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      cols = Math.ceil(w / CELL); rows = Math.ceil(h / CELL)
      heat = new Float32Array(cols * rows); rate = new Float32Array(cols * rows); lit.clear()
    }

    function lightCell(c, r, amount, cool = 0.92) {
      if (c < 0 || r < 0 || c >= cols || r >= rows) return
      const i = r * cols + c
      // A trail passing over a ping cell keeps the slower cooling.
      rate[i] = heat[i] > 0.02 ? Math.max(rate[i], cool) : cool
      heat[i] = Math.min(1, heat[i] + amount)
      lit.add(i)
    }

    function light(x, y, amount) {
      const c = Math.floor(x / CELL), r = Math.floor(y / CELL)
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const falloff = dx === 0 && dy === 0 ? 1 : (dx && dy ? 0.25 : 0.45)
          lightCell(c + dx, r + dy, amount * falloff * (0.6 + Math.random() * 0.4))
        }
      }
    }

    function stroke(p, amount) {
      if (last) {
        const dist = Math.hypot(p.x - last.x, p.y - last.y)
        const steps = Math.min(24, Math.ceil(dist / (CELL * 0.75)))
        for (let s = 1; s <= steps; s++) light(last.x + ((p.x - last.x) * s) / steps, last.y + ((p.y - last.y) * s) / steps, amount)
      } else light(p.x, p.y, amount)
      last = p
      kick()
    }

    // A ring of cells at radius `rad`, one sample per cell of circumference.
    function ring(x, y, rad, amount) {
      const n = Math.max(8, Math.ceil((Math.PI * 2 * rad) / (CELL * 0.9)))
      const seen = new Set()
      for (let k = 0; k < n; k++) {
        const a = (k / n) * Math.PI * 2
        const c = Math.floor((x + Math.cos(a) * rad) / CELL), r = Math.floor((y + Math.sin(a) * rad) / CELL)
        const key = r * cols + c
        if (seen.has(key)) continue
        seen.add(key)
        lightCell(c, r, amount * (0.75 + Math.random() * 0.25), 0.8)
      }
    }

    function frame(now) {
      raf = 0
      const dt = Math.min(0.05, prev ? (now - prev) / 1000 : 1 / 60)
      prev = now
      for (let k = pings.length - 1; k >= 0; k--) {
        const p = pings[k]
        p.age += dt
        const t = p.age - p.delay
        if (t < 0) continue
        if (t >= PING_LIFE) { pings.splice(k, 1); continue }
        const q = t / PING_LIFE
        const rad = 6 + PING_SPEED * PING_LIFE * (1 - (1 - q) ** 3) * 0.55
        ring(p.x, p.y, rad, p.strength * (1 - q) ** 1.2 * dt * 30)
      }
      // Frame-rate independent cooling, so 120 Hz phones fade at the same speed.
      const k = dt * 60
      ctx.clearRect(0, 0, w, h)
      for (const i of lit) {
        const v = (heat[i] *= Math.pow(rate[i], k))
        if (v < 0.02) { heat[i] = 0; lit.delete(i); continue }
        ctx.fillStyle = ramp[Math.min(31, Math.round(v * 31))]
        ctx.globalAlpha = 0.12 + v * 0.48
        ctx.fillRect((i % cols) * CELL + GAP / 2, Math.floor(i / cols) * CELL + GAP / 2, CELL - GAP, CELL - GAP)
      }
      ctx.globalAlpha = 1
      if (lit.size || pings.length) raf = requestAnimationFrame(frame)
      else prev = 0
    }
    const kick = () => { if (!raf) raf = requestAnimationFrame(frame) }

    resize()
    window.addEventListener('resize', resize)
    const off = []
    const on = (target, type, fn, opts = { passive: true }) => { target.addEventListener(type, fn, opts); off.push(() => target.removeEventListener(type, fn, opts)) }

    if (touch) {
      let down = null
      on(window, 'touchstart', e => {
        const t = e.touches[0]
        if (!t || e.touches.length > 1) { down = null; last = null; return }
        const target = e.target instanceof Element ? e.target : null
        down = { x: t.clientX, y: t.clientY, at: performance.now(), interactive: !!target?.closest(INTERACTIVE) }
        last = null
        if (!down.interactive) stroke({ x: t.clientX, y: t.clientY }, 0.35)
      })
      // touchmove keeps firing while the page scrolls under the thumb.
      on(window, 'touchmove', e => {
        const t = e.touches[0]
        if (!t || e.touches.length > 1) return
        stroke({ x: t.clientX, y: t.clientY }, 0.42)
      })
      on(window, 'touchend', e => {
        const t = e.changedTouches[0]
        if (down && t && !down.interactive) {
          const moved = Math.hypot(t.clientX - down.x, t.clientY - down.y)
          if (moved < 12 && performance.now() - down.at < 400) {
            // Two rings, the second a beat behind and softer: a ping and its echo.
            pings.push({ x: t.clientX, y: t.clientY, age: 0, delay: 0, strength: 1 })
            pings.push({ x: t.clientX, y: t.clientY, age: 0, delay: 0.16, strength: 0.55 })
            if (pings.length > 8) pings.splice(0, pings.length - 8)
            kick()
          }
        }
        down = null; last = null
      })
      on(window, 'touchcancel', () => { down = null; last = null })
    } else {
      on(window, 'pointermove', e => stroke({ x: e.clientX, y: e.clientY }, 0.55))
      on(document, 'pointerleave', () => { last = null })
      on(window, 'scroll', () => { last = null })
    }

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      off.forEach(f => f())
    }
  }, [])

  return <canvas ref={ref} className="pointer-events-none fixed inset-x-0 top-0 z-0 h-screen w-full [@media(hover:none)]:h-lvh" aria-hidden="true" />
}
