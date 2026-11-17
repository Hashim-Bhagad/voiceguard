import { Link } from 'react-router-dom'
import { useEffect, useMemo, useRef } from 'react'
import { WORDMARK_WIDE } from './asciiWordmark'
import { Mark } from '../components/Logo'

/*
  The footer signs off in ASCII, in the brand colours: solid blocks in amber, the
  box-drawing shadow in dim grey, so the letters read as lit from the front. Near the
  cursor the glyphs dissolve into shade blocks and settle back, the same pixel
  language as the hero meter. Reduced motion keeps the still wordmark.
*/
const SHADES = ['░', '▒', '▓', '█']
const COLS = Math.max(...WORDMARK_WIDE.map(l => l.length))

export default function AsciiFooter() {
  const pre = useRef(null)
  const grid = useMemo(() => WORDMARK_WIDE.map(l => l.padEnd(COLS, ' ').split('')), [])

  useEffect(() => {
    const el = pre.current
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    if (!window.matchMedia('(pointer: fine)').matches) return
    const cells = [...el.querySelectorAll('[data-c]')]
    const byPos = new Map(cells.map(n => [n.dataset.c, n]))
    const dirty = new Map()
    let raf = 0
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
    const onMove = e => {
      const rect = el.getBoundingClientRect()
      const cx = ((e.clientX - rect.left) / rect.width) * COLS
      const cy = ((e.clientY - rect.top) / rect.height) * grid.length
      if (cy < -2 || cy > grid.length + 2) return
      const now = performance.now()
      for (let r = 0; r < grid.length; r++) {
        for (let c = Math.max(0, Math.floor(cx - 6)); c <= Math.min(COLS - 1, Math.ceil(cx + 6)); c++) {
          if (grid[r][c] === ' ') continue
          const d = Math.hypot((c - cx) / 2.2, r - cy)
          if (d > 2.4) continue
          const key = `${r}-${c}`
          const n = byPos.get(key)
          n.textContent = SHADES[Math.min(3, Math.floor((2.4 - d) * 1.6))]
          n.classList.add('text-amber-hot')
          dirty.set(key, now + 260 + Math.random() * 280)
        }
      }
      if (!raf) raf = requestAnimationFrame(restore)
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => { window.removeEventListener('pointermove', onMove); cancelAnimationFrame(raf) }
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
