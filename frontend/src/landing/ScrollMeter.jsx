import { useEffect, useRef } from 'react'
import { token, toRgb } from '../lib/tokens'
import { isTouch, prefersReduced } from '../lib/touch'

/*
  Touch only: the scroll position as one column of the voice meter, down the right
  edge of the screen. Cells fill amber with reading progress. Scroll speed drives a
  level above the fill head (fast attack, slow release) that runs from amber to hot,
  with a peak-hold cell, so a fling reads like a shout on the meter. It appears while
  the page moves and fades out shortly after. Drawn only while visible.
*/
const CELL = 4
const PITCH = 7
const TOP = 84 // clears the floating nav
const BOTTOM = 28

export default function ScrollMeter() {
  const ref = useRef(null)

  useEffect(() => {
    if (!isTouch() || prefersReduced()) return
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    const amber = token('--amber-500'), hot = token('--amber-600'), paper = token('--paper')
    const dim = `rgb(${toRgb(token('--grey-700')).join(',')})`
    let h = 0, n = 0, dpr = 1, raf = 0
    let lastY = window.scrollY, lastT = performance.now(), prev = 0
    let level = 0, peak = 0, peakHold = 0, idleAt = 0, shown = false

    function size() {
      dpr = Math.min(window.devicePixelRatio || 1, 3)
      h = Math.max(0, window.innerHeight - TOP - BOTTOM)
      n = Math.floor(h / PITCH)
      canvas.style.height = `${n * PITCH}px`
      canvas.width = Math.round(CELL * dpr); canvas.height = Math.round(n * PITCH * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    function draw() {
      const max = document.documentElement.scrollHeight - window.innerHeight
      const progress = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0
      const head = Math.round(progress * (n - 1))
      ctx.clearRect(0, 0, CELL, n * PITCH)
      const lvl = Math.round(level * 9), pk = Math.round(peak * 9)
      for (let i = 0; i < n; i++) {
        const y = i * PITCH
        let color = dim, alpha = 0.55
        if (i < head) { color = amber; alpha = 0.35 + 0.45 * (i / Math.max(1, head)) }
        else if (i === head) { color = paper; alpha = 1 }
        else if (i - head <= lvl) { color = i - head > 5 ? hot : amber; alpha = 0.95 - (i - head) * 0.06 }
        else if (pk > lvl && i - head === pk) { color = paper; alpha = 0.6 }
        ctx.globalAlpha = alpha
        ctx.fillStyle = color
        ctx.fillRect(0, y, CELL, CELL)
      }
      ctx.globalAlpha = 1
    }

    function frame(now) {
      raf = 0
      const dt = Math.min(0.05, prev ? (now - prev) / 1000 : 1 / 60)
      prev = now
      const decay = Math.pow(0.88, dt * 60)
      level *= decay
      if ((peakHold -= dt) <= 0) peak = Math.max(level, peak - dt * 0.9)
      draw()
      if (now > idleAt && shown) { shown = false; canvas.style.opacity = '0' }
      // Keep drawing while the level is still falling or the fade is running.
      if (level > 0.01 || peak > level + 0.01 || shown) raf = requestAnimationFrame(frame)
      else prev = 0
    }

    function onScroll() {
      const now = performance.now()
      const y = window.scrollY
      const v = Math.abs(y - lastY) / Math.max(8, now - lastT) // px per ms
      lastY = y; lastT = now
      // About 3 px/ms (a firm fling) fills the level.
      const target = Math.min(1, v / 3)
      if (target > level) level += (target - level) * 0.6
      if (level >= peak) { peak = level; peakHold = 0.5 }
      idleAt = now + 900
      if (!shown) { shown = true; canvas.style.opacity = '1' }
      if (!raf) raf = requestAnimationFrame(frame)
    }

    size()
    window.addEventListener('resize', size)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', size)
      window.removeEventListener('scroll', onScroll)
    }
  }, [])

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className="pointer-events-none fixed right-[5px] z-40 w-[4px] opacity-0 transition-opacity duration-500 [@media(hover:hover)]:hidden"
      style={{ top: TOP }}
    />
  )
}
