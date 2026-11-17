import { useEffect, useRef } from 'react'
import { token, toRgb as rgbOf } from '../lib/tokens'

/*
  The demo's instrument: a phone line drawn as a pixel scope. Audio enters on the
  right and scrolls left past a read head. Whatever passes the head has been
  "heard", and turns the colour of what was heard.

    idle     line hiss, grey, barely moving: the line is open, nobody is talking
    preview  hovering a call: the line swells with that caller's voice, amber
    running  the voice at full level; past the head it heats from amber to orange
    result   the head stamps the verdict colour back across the heard audio

  Voices differ the way the hero meter taught: a person is irregular, a clone keeps
  one beat. `jitter` comes from the scenario, so the clone call looks too clean.
*/

const PITCH = 8
const GAP = 2
const HEAD = 0.72 // read head position across the width

const mix = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]

export default function LineScope({ mode = 'idle', tone = null, jitter = 1, className = '' }) {
  const ref = useRef(null)
  const state = useRef({ mode, tone, jitter })
  const redraw = useRef(null)
  useEffect(() => {
    state.current = { mode, tone, jitter, changedAt: performance.now() }
    redraw.current?.()
  }, [mode, tone, jitter])

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const C = {
      grey: rgbOf(token('--grey-700')),
      amber: rgbOf(token('--amber-500')),
      hot: rgbOf(token('--amber-600')),
      paper: rgbOf(token('--paper')),
      high: rgbOf(token('--red-500')),
      caution: rgbOf(token('--yellow-400')),
      safe: rgbOf(token('--mint-400')),
    }
    let w = 0, h = 0, cols = 0, rows = 0
    // Newest column first. Each: amplitude 0..1, colour (rgb), heard flag.
    let lines = []
    let offset = 0, t = 0, last = performance.now(), raf = 0, visible = true
    let level = 0.05 // smoothed loudness
    let beat = 0

    function layout() {
      const r = canvas.getBoundingClientRect()
      w = r.width; h = r.height
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      cols = Math.ceil(w / PITCH) + 2
      rows = Math.max(6, Math.floor(h / PITCH / 2))
      while (lines.length < cols) lines.push({ a: 0.04, c: [...C.grey], heard: false })
      lines.length = cols
    }

    // Loudness of the next column of audio.
    function sample() {
      const { mode: m, jitter: j } = state.current
      const target = m === 'idle' ? 0.06 : m === 'preview' ? 0.5 : m === 'running' ? 0.92 : 0.22
      level += (target - level) * 0.08
      // An open line: hiss, and now and then a faint click.
      if (m === 'idle') return Math.random() < 0.015 ? 0.18 + Math.random() * 0.12 : 0.03 + Math.random() * 0.07
      beat += 1
      const human = Math.min(1, j / 1.2) // 0 = clone-clean, 1 = person
      // A person: syllables of varying length and pauses. A clone: one steady beat.
      const syll = human > 0.5
        ? Math.max(0, Math.sin(t * 7.3 + Math.sin(t * 1.9) * 2.4)) * (Math.sin(t * 0.8) > -0.6 ? 1 : 0.15)
        : Math.round((0.5 + 0.5 * Math.sin(beat * 0.55)) * 4) / 4
      const grain = human > 0.5 ? Math.random() * 0.45 : 0.12
      return Math.min(1, level * (0.25 + 0.75 * syll) + level * grain * 0.5)
    }

    function colourFor(isHeard) {
      const { mode: m, tone: tn } = state.current
      if (m === 'idle') return C.grey
      if (m === 'result' && tn && C[tn]) return C[tn]
      return isHeard ? C.hot : C.amber
    }

    function draw() {
      ctx.clearRect(0, 0, w, h)
      const mid = Math.floor(h / 2 / PITCH) * PITCH
      const headX = Math.round((w * HEAD) / PITCH) * PITCH
      const cell = PITCH - GAP
      for (let i = 0; i < lines.length; i++) {
        const L = lines[i]
        const x = w - (i + 1) * PITCH + offset
        if (x < -PITCH) break
        const n = Math.max(1, Math.round(L.a * (rows - 2)))
        const [r, g, b] = L.c
        for (let k = 0; k < n; k++) {
          // Brighter towards the centre line, like signal over noise.
          ctx.fillStyle = `rgba(${r | 0},${g | 0},${b | 0},${(0.95 - (k / rows) * 0.55).toFixed(3)})`
          ctx.fillRect(x, mid - (k + 1) * PITCH + GAP, cell, cell)
          ctx.fillRect(x, mid + k * PITCH, cell, cell)
        }
      }
      // The read head.
      const m = state.current.mode
      if (m !== 'idle') {
        const [r, g, b] = m === 'result' && state.current.tone && C[state.current.tone] ? C[state.current.tone] : C.paper
        for (let y = PITCH; y < h - PITCH; y += PITCH) {
          ctx.fillStyle = `rgba(${r},${g},${b},${m === 'running' ? 0.55 : 0.28})`
          ctx.fillRect(headX + 2, y + 2, 2, 2)
        }
      }
    }

    function step(now) {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now; t += dt
      const m = state.current.mode
      const speed = m === 'idle' ? 26 : m === 'result' ? 46 : m === 'running' ? 170 : 120 // px per second
      offset += speed * dt
      while (offset >= PITCH) {
        offset -= PITCH
        lines.unshift({ a: sample(), c: [...colourFor(false)], heard: false })
        lines.length = cols
      }
      const headIndex = Math.floor((w * (1 - HEAD)) / PITCH)
      const since = (now - (state.current.changedAt || 0)) / 1000
      for (let i = 0; i < lines.length; i++) {
        const L = lines[i]
        let goal
        if (m === 'result') {
          // The verdict spreads out from the head, a column every 12 ms.
          const reach = since / 0.012
          goal = Math.abs(i - headIndex) < reach ? colourFor(true) : (i > headIndex ? C.hot : C.amber)
        } else {
          L.heard = i > headIndex
          goal = colourFor(L.heard)
        }
        L.c = mix(L.c, goal, 0.12)
      }
      draw()
    }

    function loop(now) {
      raf = 0
      if (!visible || document.hidden) return
      step(now)
      raf = requestAnimationFrame(loop)
    }
    const start = () => { if (!raf && !reduced) { last = performance.now(); raf = requestAnimationFrame(loop) } }

    layout()
    if (reduced) {
      // One settled frame, redrawn when the mode changes.
      redraw.current = () => {
        for (let i = 0; i < cols; i++) { t += 0.03; lines.unshift({ a: sample(), c: [...colourFor(true)], heard: true }) }
        lines.length = cols
        draw()
      }
      redraw.current()
    } else start()

    const ro = new ResizeObserver(() => { layout(); draw() })
    ro.observe(canvas)
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) start() })
    io.observe(canvas)
    const onVis = () => { if (!document.hidden) start() }
    document.addEventListener('visibilitychange', onVis)
    return () => { redraw.current = null; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); document.removeEventListener('visibilitychange', onVis) }
  }, [])

  return <canvas ref={ref} className={`block h-full w-full ${className}`} aria-hidden="true" />
}
