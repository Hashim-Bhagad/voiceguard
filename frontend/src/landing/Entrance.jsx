import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import PixelMorph from '../components/PixelMorph'
import { token } from '../lib/tokens'

/*
  The title card, once per browser session (index.html marks repeat visits before
  first paint). The pixel grid listens (a live meter), checks (a shield) and lands
  on the VoiceGuard mark. Then the black breaks into cells that clear outward from
  the centre, so the page underneath arrives through the same pixels. About 2.4 s,
  any click or key skips it, and reduced motion never sees it.
*/
const LABEL = { wave: 'Listening', shield: 'Checking the voice', mark: 'VoiceGuard' }
const CELL = 44

function Dissolve({ onEnd }) {
  const ref = useRef(null)
  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    const w = window.innerWidth, h = window.innerHeight
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = w * dpr; canvas.height = h * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    const bg = token('--background')
    const amber = token('--amber-500')
    const cols = Math.ceil(w / CELL), rows = Math.ceil(h / CELL)
    const cx = cols / 2, cy = rows / 2, far = Math.hypot(cx, cy)
    const at = []
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      at.push(0.04 + (Math.hypot(c + 0.5 - cx, r + 0.5 - cy) / far) * 0.42 + Math.random() * 0.12)
    }
    const start = performance.now()
    let raf = 0
    const frame = now => {
      const t = (now - start) / 1000
      ctx.clearRect(0, 0, w, h)
      let left = 0
      for (let i = 0; i < at.length; i++) {
        const d = at[i] - t
        if (d < 0) continue
        left++
        const x = (i % cols) * CELL, y = Math.floor(i / cols) * CELL
        ctx.fillStyle = bg
        ctx.fillRect(x, y, CELL + 0.5, CELL + 0.5)
        // The front of the wave lights a thin amber cell before it clears.
        if (d < 0.07) {
          ctx.globalAlpha = 0.22 * (1 - d / 0.07)
          ctx.fillStyle = amber
          ctx.fillRect(x + 6, y + 6, CELL - 12, CELL - 12)
          ctx.globalAlpha = 1
        }
      }
      if (left) raf = requestAnimationFrame(frame)
      else onEnd()
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [onEnd])
  return <canvas ref={ref} className="fixed inset-0 z-[70] h-full w-full" aria-hidden="true" />
}

export default function Entrance({ onReveal }) {
  const [show] = useState(() => {
    if (typeof window === 'undefined') return false
    if (document.documentElement.dataset.entrance === 'done') return false
    return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })
  // card → dissolving → gone
  const [stage, setStage] = useState(show ? 'card' : 'gone')
  const [phase, setPhase] = useState('wave')
  const done = useRef(false)
  const finish = useCallback(() => {
    if (done.current) return
    done.current = true
    try { sessionStorage.setItem('tv-entrance', '1') } catch { /* private mode */ }
    document.documentElement.dataset.entrance = 'done'
    setStage(show ? 'dissolving' : 'gone')
    onReveal?.()
  }, [show, onReveal])

  useEffect(() => {
    if (!show) { finish(); return }
    const safety = setTimeout(finish, 3200)
    const skip = () => finish()
    window.addEventListener('pointerdown', skip, { once: true })
    window.addEventListener('keydown', skip, { once: true })
    return () => {
      clearTimeout(safety)
      window.removeEventListener('pointerdown', skip)
      window.removeEventListener('keydown', skip)
    }
  }, [show, finish])

  const onEnd = useCallback(() => setStage('gone'), [])

  return (
    <>
      {stage === 'dissolving' && <Dissolve onEnd={onEnd} />}
      <AnimatePresence>
        {stage === 'card' && (
          <motion.div
            key="entrance"
            aria-hidden="true"
            className="fixed inset-0 z-[71] grid place-items-center bg-background"
            exit={{ opacity: 0, transition: { duration: 0.16 } }}
          >
            <div className="flex flex-col items-center gap-8">
              <PixelMorph size={132} onPhase={setPhase} onDone={finish} />
              <div className="relative h-6 w-64 text-center">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.p
                    key={phase}
                    className={phase === 'mark'
                      ? 'text-lg font-semibold tracking-[-0.02em] text-foreground'
                      : 'label-mono pt-1'}
                    initial={{ opacity: 0, y: 6, filter: 'blur(4px)' }}
                    animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                    exit={{ opacity: 0, y: -6, filter: 'blur(4px)' }}
                    transition={{ duration: 0.18 }}
                  >
                    {LABEL[phase]}
                  </motion.p>
                </AnimatePresence>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
