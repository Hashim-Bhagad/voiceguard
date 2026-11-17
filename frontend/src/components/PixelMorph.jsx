import { useEffect, useRef } from 'react'
import { token as css, toRgb } from '../lib/tokens'

/*
  The loader is the logo being built. One 15 x 15 grid of square cells passes through
  three shapes: a live voice meter, a shield, then the VoiceGuard mark (four pixel
  columns, the tallest amber). Cells change in a ripple from the centre, and a cell
  mid-change flickers once, so the shape reads as reassembled rather than cross-faded.

  Canvas 2D. `loop` cycles forever (route loading); otherwise it plays once, holds on
  the mark and calls onDone. Reduced motion draws the mark and stops.
*/

const N = 15
const PHASES = ['wave', 'shield', 'mark']
const DUR = { wave: 0.8, shield: 0.72, mark: 0.6 }
const HOLD = 0.4 // the finished mark holds before onDone
const RIPPLE = 0.28 // seconds from the centre cell to the corner cell


function hash(n) {
  const s = Math.sin(n * 91.7) * 43758.5453
  return s - Math.floor(s)
}

// Shield silhouette in grid units, sampled once.
function shieldMask() {
  const c = document.createElement('canvas').getContext('2d')
  const p = new Path2D()
  p.moveTo(7.5, 0.6)
  p.lineTo(13.6, 2.8)
  p.lineTo(13.6, 7.2)
  p.bezierCurveTo(13.6, 11, 10.8, 13.2, 7.5, 14.5)
  p.bezierCurveTo(4.2, 13.2, 1.4, 11, 1.4, 7.2)
  p.lineTo(1.4, 2.8)
  p.closePath()
  // The check mark, cut out of the shield.
  const seg = (px, py, ax, ay, bx, by) => {
    const dx = bx - ax, dy = by - ay
    const k = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return Math.hypot(px - ax - k * dx, py - ay - k * dy)
  }
  const onCheck = (x, y) => Math.min(seg(x, y, 4.5, 7.5, 6.5, 9.5), seg(x, y, 6.5, 9.5, 10.5, 5.5)) < 0.78
  const mask = []
  for (let r = 0; r < N; r++) for (let col = 0; col < N; col++) {
    const inside = c.isPointInPath(p, col + 0.5, r + 0.5)
    mask.push(inside ? (onCheck(col + 0.5, r + 0.5) ? 2 : 1) : 0)
  }
  return mask
}

// The mark: columns 3 wide with a 1-cell gap, blocks 2 tall with a 1-cell gap.
function markMask() {
  const heights = [2, 4, 3, 5]
  const mask = new Array(N * N).fill(0)
  heights.forEach((h, i) => {
    for (let b = 0; b < h; b++) {
      for (let dr = 0; dr < 2; dr++) {
        const r = N - 1 - b * 3 - dr
        for (let dc = 0; dc < 3; dc++) mask[r * N + i * 4 + dc] = i === 3 ? 3 : 1
      }
    }
  })
  return mask
}

export default function PixelMorph({ size = 120, loop = false, onPhase, onDone, className = '' }) {
  const ref = useRef(null)
  const cb = useRef({ onPhase, onDone })
  useEffect(() => { cb.current = { onPhase, onDone } })

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = size * dpr; canvas.height = size * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const amber = toRgb(css('--amber-500'))
    const hot = toRgb(css('--amber-600'))
    const paper = toRgb(css('--paper'))
    const shield = shieldMask()
    const mark = markMask()

    const pitch = size / N
    const gap = Math.max(1, pitch * 0.2)
    const cell = pitch - gap
    const dist = []
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      dist.push(Math.hypot(c - 7, r - 7) / Math.hypot(7, 7))
    }

    // Each phase answers: how lit is this cell, and in what colour, at time t.
    function goal(phase, i, t) {
      const r = Math.floor(i / N), c = i % N
      if (phase === 'wave') {
        const syll = 0.55 + 0.45 * Math.sin(t * 5.2 + Math.sin(t * 1.3) * 2)
        const h = 2 + (N - 3) * syll * (0.35 + 0.65 * Math.abs(Math.sin(t * (3 + hash(c) * 3) + hash(c + 4) * 6.28)))
          * Math.exp(-((c - 7) ** 2) / 40)
        const fromBottom = N - 1 - r
        if (c % 2 === 1) return [0, amber]
        if (fromBottom >= Math.round(h)) return [0, amber]
        return [0.45 + 0.55 * (fromBottom + 1) / Math.max(3, h), fromBottom / N > 0.62 ? hot : amber]
      }
      if (phase === 'shield') {
        const m = shield[i]
        if (m === 2) return [0.08, paper]
        if (m === 1) return [0.5 + 0.5 * (1 - r / N), amber]
        return [0, amber]
      }
      const m = mark[i]
      if (m === 3) return [1, amber]
      if (m) return [0.45 + 0.4 * (1 - r / N), paper]
      return [0, paper]
    }

    const val = new Float32Array(N * N)
    const col = Array.from({ length: N * N }, () => [...amber])
    let phaseIdx = 0, phaseStart = 0, t = 0, raf = 0, ended = false
    const t0 = performance.now()
    let prevNow = t0
    cb.current.onPhase?.(PHASES[0])

    function draw() {
      ctx.clearRect(0, 0, size, size)
      for (let i = 0; i < N * N; i++) {
        const v = val[i]
        if (v < 0.02) continue
        const r = Math.floor(i / N), c = i % N
        const [R, G, B] = col[i]
        ctx.fillStyle = `rgba(${R | 0},${G | 0},${B | 0},${v.toFixed(3)})`
        ctx.fillRect(c * pitch + gap / 2, r * pitch + gap / 2, cell, cell)
      }
    }

    if (reduced) {
      for (let i = 0; i < N * N; i++) { const [v, rgb] = goal('mark', i, 0); val[i] = v; col[i] = [...rgb] }
      draw()
      cb.current.onPhase?.('mark')
      const id = setTimeout(() => cb.current.onDone?.(), 300)
      return () => clearTimeout(id)
    }

    function frame(now) {
      // Wall-clock phases: a slow device drops frames, never the logo.
      t = (now - t0) / 1000
      const dt = Math.min(0.1, (now - prevNow) / 1000)
      prevNow = now
      let phase = PHASES[phaseIdx]
      const local = t - phaseStart
      if (local > DUR[phase]) {
        if (phaseIdx < PHASES.length - 1 || loop) {
          phaseIdx = (phaseIdx + 1) % PHASES.length
          phaseStart = t
          phase = PHASES[phaseIdx]
          cb.current.onPhase?.(phase)
        } else if (!ended && local > DUR[phase] + HOLD) {
          ended = true
          cb.current.onDone?.()
        }
      }
      const prev = PHASES[(phaseIdx + PHASES.length - 1) % PHASES.length]
      const sinceSwitch = t - phaseStart
      for (let i = 0; i < N * N; i++) {
        // The ripple: a cell keeps the old shape until the wave front reaches it.
        const delay = dist[i] * RIPPLE + hash(i) * 0.06
        const first = phaseIdx === 0 && !loop
        const use = first || sinceSwitch >= delay ? phase : prev
        let [v, rgb] = goal(use, i, t)
        // One flicker as the front passes, only on cells that belong to either shape.
        const d = sinceSwitch - delay
        if (!first && d > -0.04 && d < 0.06 && hash(i + Math.floor(t * 30)) > 0.5) {
          const other = goal(use === phase ? prev : phase, i, t)[0]
          if (v > 0.05 || other > 0.05) v = Math.max(v, 0.95)
        }
        // Time-based easing, so a dropped frame doesn't leave the old shape behind.
        const k = 1 - Math.exp(-dt * (use === 'wave' ? 40 : 16))
        const kc = 1 - Math.exp(-dt * 16)
        val[i] += (v - val[i]) * k
        const cc = col[i]
        cc[0] += (rgb[0] - cc[0]) * kc; cc[1] += (rgb[1] - cc[1]) * kc; cc[2] += (rgb[2] - cc[2]) * kc
      }
      draw()
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [size, loop])

  return <canvas ref={ref} style={{ width: size, height: size }} className={`block ${className}`} aria-hidden="true" />
}
