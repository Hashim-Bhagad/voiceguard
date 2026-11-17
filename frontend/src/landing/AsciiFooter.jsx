import { Link } from 'react-router-dom'
import { useEffect, useMemo, useRef } from 'react'
import { WORDMARK_WIDE } from './asciiWordmark'
import { Mark } from '../components/Logo'
import { isTouch, prefersReduced } from '../lib/touch'

/*
  The footer signs off in ASCII, in the brand colours: solid blocks in amber, the
  box-drawing shadow in dim grey, so the letters read as lit from the front. Near the
  cursor (or under the thumb, on a phone) the glyphs dissolve into shade blocks and
  settle back, the same pixel language as the hero meter. On touch screens a scan
  bar also sweeps across the wordmark as it comes into view. Reduced motion keeps the still wordmark.
*/
const SHADES = ['░', '▒', '▓', '█']
const COLS = Math.max(...WORDMARK_WIDE.map(l => l.length))

export default function AsciiFooter() {
  const pre = useRef(null)
  const grid = useMemo(() => WORDMARK_WIDE.map(l => l.padEnd(COLS, ' ').split('')), [])

  useEffect(() => {
    const el = pre.current
    if (!el || prefersReduced()) return
    const fine = window.matchMedia('(pointer: fine)').matches
    const touch = isTouch()
    if (!fine && !touch) return
    const cells = [...el.querySelectorAll('[data-c]')]
    const byPos = new Map(cells.map(n => [n.dataset.c, n]))
    const dirty = new Map()
    let raf = 0, sweepRaf = 0
    const restore = () => {
      raf = 0
      const now = performance.now()
      for (const [key, until] of dirty) {
        if (now < until) continue
        const n = byPos.get(key)
        n.textContent = n.dataset.g
        n.classList.remove('text-amber-hot')
        dirty.delete(key)
      }
      if (dirty.size) raf = requestAnimationFrame(restore)
    }
    // Shade one glyph by its distance from the source (0 = full block).
    const shade = (r, c, d, reach, hold) => {
      if (grid[r]?.[c] === undefined || grid[r][c] === ' ' || d > reach) return
      const n = byPos.get(`${r}-${c}`)
      n.textContent = SHADES[Math.min(3, Math.floor(((reach - d) / reach) * 4))]
      n.classList.add('text-amber-hot')
      dirty.set(`${r}-${c}`, performance.now() + hold + Math.random() * 280)
    }
    const dissolveAt = (clientX, clientY, reach = 2.4) => {
      const rect = el.getBoundingClientRect()
      const cx = ((clientX - rect.left) / rect.width) * COLS
      const cy = ((clientY - rect.top) / rect.height) * grid.length
      if (cy < -2 || cy > grid.length + 2) return
      for (let r = 0; r < grid.length; r++) {
        for (let c = Math.max(0, Math.floor(cx - 7)); c <= Math.min(COLS - 1, Math.ceil(cx + 7)); c++) {
          shade(r, c, Math.hypot((c - cx) / 2.2, r - cy), reach, 260)
        }
      }
      if (!raf) raf = requestAnimationFrame(restore)
    }
    const off = []
    const on = (t, type, fn, o = { passive: true }) => { t.addEventListener(type, fn, o); off.push(() => t.removeEventListener(type, fn, o)) }

    if (touch) {
      // A thumb dragged across the wordmark rubs the glyphs into shade, a little wider
      // than the cursor version since a fingertip covers more.
      on(window, 'touchmove', e => { const t = e.touches[0]; if (t) dissolveAt(t.clientX, t.clientY, 3.2) })
      on(window, 'touchstart', e => { const t = e.touches[0]; if (t) dissolveAt(t.clientX, t.clientY, 3.2) })
      // Each time the wordmark comes fully into view, a scan bar sweeps across it left
      // to right, the way a meter reads a signal, then the letters settle back.
      let lastSweep = 0
      const sweep = () => {
        const t0 = performance.now()
        const step = now => {
          const p = Math.min(1, (now - t0) / 1100)
          const x = -4 + (COLS + 8) * (1 - (1 - p) ** 2)
          for (let r = 0; r < grid.length; r++) {
            for (let c = Math.max(0, Math.floor(x - 3)); c <= Math.min(COLS - 1, Math.ceil(x + 1)); c++) {
              shade(r, c, Math.abs(c - x) * (c > x ? 1.6 : 0.7), 2.6, 120)
            }
          }
          if (!raf) raf = requestAnimationFrame(restore)
          sweepRaf = p < 1 ? requestAnimationFrame(step) : 0
        }
        sweepRaf = requestAnimationFrame(step)
      }
      const io = new IntersectionObserver(([e]) => {
        if (e.isIntersecting && performance.now() - lastSweep > 2500) { lastSweep = performance.now(); sweep() }
      }, { threshold: 0.9 })
      io.observe(el)
      off.push(() => io.disconnect())
    } else {
      on(window, 'pointermove', e => dissolveAt(e.clientX, e.clientY))
    }
    return () => { off.forEach(f => f()); cancelAnimationFrame(raf); cancelAnimationFrame(sweepRaf) }
  }, [grid])

  return (
    <footer className="relative overflow-hidden border-t border-hairline px-6 pb-10 pt-16 sm:px-8">
      <div className="mx-auto max-w-[1240px]">
        <p className="sr-only">VoiceGuard</p>
        <pre
          ref={pre}
          aria-hidden="true"
          className="select-none overflow-hidden font-mono leading-[1.05] tracking-[0]"
          style={{ fontSize: `min(calc((100vw - 48px) / ${COLS} / 0.6), 1.05rem)` }}
        >
          {grid.map((row, r) => (
            <span key={r} className="block">
              {row.map((g, c) => (
                <span key={c} data-c={`${r}-${c}`} data-g={g} className={g === '█' ? 'text-accent' : g === ' ' ? '' : 'text-grey-700'}>{g}</span>
              ))}
            </span>
          ))}
        </pre>
        <div className="mt-14 flex flex-col gap-8 text-sm sm:flex-row sm:items-end sm:justify-between">
          <div className="flex items-center gap-3 text-muted">
            <Mark className="size-5" />
            <span>Deepfake voice detection for English, Hindi, Bengali, Tamil and Marathi.</span>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-muted">
            <a className="hover:text-foreground" href="https://github.com/Hashim-Bhagad/voiceguard" target="_blank" rel="noreferrer">GitHub</a>
            <a className="hover:text-foreground" href="https://huggingface.co/Hashim-Bhagad/voiceguard-xlsr-aasist-indic" target="_blank" rel="noreferrer">Model on Hugging Face</a>
            <Link className="hover:text-foreground" to="/dashboard">Workspace</Link>
          </nav>
        </div>
        <p className="mt-10 font-mono text-xs text-muted">A risk signal, not proof of identity. Non-commercial research model (CC-BY-NC-4.0).</p>
      </div>
    </footer>
  )
}
