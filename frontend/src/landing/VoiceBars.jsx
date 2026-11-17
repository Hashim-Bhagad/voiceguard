import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { token as css } from '../lib/tokens'

/*
  The signature move: a pixel voice meter that reacts to the cursor and exposes the
  clone. The left half moves like a human voice (irregular syllables, breath). The
  right half moves like a synthetic one: every column on the same beat, heights
  snapped to coarse steps, the odd glitch. When the cursor is on the clone side
  those cells turn the danger colour and the parent's readout flips to SYNTHETIC.

  Canvas 2D, square cells, fast attack / slow release with a peak-hold cell, like a
  studio VU meter. Pauses when off screen or the tab is hidden; reduced motion gets
  one still frame that only redraws when the pointer moves.
*/


function hash(n) {
  const s = Math.sin(n * 127.1) * 43758.5453
  return s - Math.floor(s)
}

const VoiceBars = forwardRef(function VoiceBars(
  { onSide, density = 1, calm = false, className = '', ariaLabel },
  ref,
) {
  const canvasRef = useRef(null)
  const api = useRef({ rise: 1, riseTarget: 1 })

  useImperativeHandle(ref, () => ({
    // Entrance: collapse to a flat line, then grow back over `ms`.
    flatten() { api.current.rise = 0; api.current.riseTarget = 0 },
    rise(ms = 900) { api.current.riseTarget = 1; api.current.riseMs = ms },
  }))

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const finePointer = window.matchMedia('(pointer: fine)').matches
    const colors = {
      amber: css('--amber-500'),
      hot: css('--amber-600'),
      danger: css('--red-500'),
      paper: css('--paper'),
    }

    let w = 0, h = 0, dpr = 1, cols = 0, rows = 0, cell = 0, gap = 0, ox = 0
    let level = [], peak = [], peakHold = []
    const pointer = { x: -1, y: 0.5, active: false, lastMove: 0 }
    let side = null
    let visible = true, raf = 0, last = performance.now(), t = 0

    function layout() {
      const rect = canvas.getBoundingClientRect()
      w = rect.width; h = rect.height
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const target = (w < 640 ? 9 : 13) / density
      cols = Math.max(24, Math.floor(w / target))
      const pitch = w / cols
      gap = Math.max(1.5, pitch * 0.22)
      cell = pitch - gap
      rows = Math.max(8, Math.floor(h / pitch))
      ox = (w - cols * pitch + gap) / 2
      level = Array.from({ length: cols }, (_, i) => level[i] ?? 0.08)
      peak = Array.from({ length: cols }, (_, i) => peak[i] ?? 0.1)
      peakHold = Array.from({ length: cols }, () => 0)
    }

    // Target height (0..1) for a column at time t.
    function target(c, time) {
      const x = c / (cols - 1)
      // The calm meter (closing section) is all human: no clone half, no red.
      const clone = !calm && x >= 0.5
      const px = pointer.x
      // A slow speech-like envelope shared across the meter.
      const syllable = 0.5 + 0.5 * Math.sin(time * 2.1 + Math.sin(time * 0.7) * 2)
      let v
      if (!clone) {
        // Human: each column its own phase and rate, breathy and irregular.
        const a = Math.sin(time * (2.3 + hash(c) * 2.4) + hash(c + 9) * 6.28)
        const b = Math.sin(time * (0.9 + hash(c + 3)) + c * 0.31)
        const formant = Math.exp(-((x - 0.18 - 0.08 * Math.sin(time * 0.6)) ** 2) / 0.02)
        v = 0.16 + 0.22 * (0.5 + 0.5 * a) * syllable + 0.12 * (0.5 + 0.5 * b) + 0.28 * formant * syllable
      } else {
        // Clone: one shared beat, mirrored and too clean.
        const beat = 0.5 + 0.5 * Math.sin(time * 3.2)
        const shape = 0.55 + 0.45 * Math.cos((x - 0.75) * 14)
        v = 0.18 + 0.42 * beat * shape
        if (hash(Math.floor(time * 6) * 31 + c) > 0.985) v = 0.95 // glitch spike
      }
      if (calm) v *= 0.55
      // Cursor bump: a bell around the pointer, taller near the top of the frame.
      if (px >= 0) {
        const gain = 0.35 + 0.55 * (1 - pointer.y)
        v += gain * Math.exp(-((x - px) ** 2) / 0.006)
      }
      v = Math.min(1, Math.max(0.04, v))
      if (clone) {
        const steps = Math.max(4, Math.round(rows / 4))
        v = Math.round(v * steps) / steps // snapped to coarse steps
      }
      return v
    }

    function draw() {
      ctx.clearRect(0, 0, w, h)
      const pitch = cell + gap
      const cloneLit = side === 'clone'
      const rise = api.current.rise
      for (let c = 0; c < cols; c++) {
        const x = ox + c * pitch
        const onClone = !calm && c / (cols - 1) >= 0.5
        const lit = Math.max(1, Math.round(level[c] * rows * rise))
        for (let r = 0; r < lit; r++) {
          const y = h - (r + 1) * pitch + gap
          const frac = r / rows
          let color = frac > 0.68 ? colors.hot : colors.amber
          if (onClone && cloneLit) color = colors.danger
          ctx.globalAlpha = 0.28 + 0.72 * Math.min(1, (r + 1) / Math.max(3, lit))
          ctx.fillStyle = color
          ctx.fillRect(x, y, cell, cell)
        }
        // Peak-hold cell, a beat above the column, slowly falling.
        const pr = Math.round(peak[c] * rows * rise)
        if (pr > lit) {
          ctx.globalAlpha = 0.5
          ctx.fillStyle = onClone && cloneLit ? colors.danger : colors.paper
          ctx.fillRect(x, h - (pr + 1) * pitch + gap, cell, cell)
        }
      }
      ctx.globalAlpha = 1
    }

    function step(now) {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      t += dt
      // Without a fine pointer (touch) or before the first move, a slow automatic
      // sweep shows the human/clone split on its own.
      if (!pointer.active || now - pointer.lastMove > 4000) {
        pointer.x = 0.5 + 0.42 * Math.sin(t * 0.32)
        pointer.y = 0.45 + 0.2 * Math.sin(t * 0.5)
      }
      const nextSide = calm || pointer.x < 0 ? null : pointer.x >= 0.5 ? 'clone' : 'human'
      if (nextSide !== side) { side = nextSide; onSide?.(side) }
      const a = api.current
      if (a.rise !== a.riseTarget) {
        const k = dt / ((a.riseMs || 900) / 1000)
        a.rise = Math.min(a.riseTarget, a.rise + k)
      }
      for (let c = 0; c < cols; c++) {
        const goal = target(c, t)
        const attack = goal > level[c] ? 0.6 : 0.13 // per 30 fps step
        level[c] += (goal - level[c]) * attack
        if (level[c] >= peak[c]) { peak[c] = level[c] + 1 / rows; peakHold[c] = 0.45 }
        else if ((peakHold[c] -= dt) <= 0) peak[c] = Math.max(level[c], peak[c] - dt * 0.35)
      }
      draw()
    }

    // 30 fps: the meter moves in whole cells, so 60 looks the same at twice the cost.
    let lastStep = 0
    function loop(now) {
      raf = 0
      if (!visible || document.hidden) return
      if (now - lastStep >= 32) { lastStep = now; step(now) }
      raf = requestAnimationFrame(loop)
    }
    function start() { if (!raf && !reduced) { last = performance.now(); raf = requestAnimationFrame(loop) } }
    function stillFrame() {
      // Reduced motion: settle the meter instantly and draw once.
      for (let c = 0; c < cols; c++) { level[c] = target(c, 1.7); peak[c] = level[c] + 1 / rows }
      api.current.rise = 1
      side = pointer.x < 0 ? null : pointer.x >= 0.5 ? 'clone' : 'human'
      onSide?.(side)
      draw()
    }

    function onMove(e) {
      const rect = canvas.getBoundingClientRect()
      const x = (e.clientX - rect.left) / rect.width
      const y = (e.clientY - rect.top) / rect.height
      if (y < -0.25 || y > 1.25) return
      pointer.x = Math.min(1, Math.max(0, x)); pointer.y = Math.min(1, Math.max(0, y))
      pointer.active = true; pointer.lastMove = performance.now()
      if (reduced) stillFrame()
    }

    layout()
    if (reduced) { pointer.x = 0.25; stillFrame() } else start()

    const ro = new ResizeObserver(() => { layout(); if (reduced) stillFrame() })
    ro.observe(canvas)
    const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) start() })
    io.observe(canvas)
    const onVis = () => { if (!document.hidden) start() }
    document.addEventListener('visibilitychange', onVis)
    if (finePointer) window.addEventListener('pointermove', onMove, { passive: true })

    return () => {
      cancelAnimationFrame(raf); ro.disconnect(); io.disconnect()
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('pointermove', onMove)
    }
  }, [onSide, density, calm])

  return <canvas ref={canvasRef} className={`block h-full w-full ${className}`} role="img" aria-label={ariaLabel || 'Animated voice meter'} />
})

export default VoiceBars
