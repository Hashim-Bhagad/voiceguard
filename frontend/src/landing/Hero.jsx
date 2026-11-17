import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion, useScroll, useTransform } from 'motion/react'
import { Dithering } from '@paper-design/shaders-react'
import VoiceBars from './VoiceBars'
import Cta from './Cta'
import useTilt from './useTilt'
import { haptic, isTouch } from '../lib/touch'

const EASE = [0.16, 1, 0.3, 1]

// The dithered wave, stepped 12 times a second instead of the shader's 60. The wave
// is slow and the pattern is pixel art, so the lower rate reads the same and costs a
// fifth. Renders at native pixel ratio, pauses off screen and in hidden tabs.
const DITHER_FPS = 12
function DitherWave({ reduce }) {
  const wrap = useRef(null)
  const [frame, setFrame] = useState(0)
  useEffect(() => {
    if (reduce) return
    let id = 0, visible = true
    const tick = () => setFrame(f => f + (1000 / DITHER_FPS) * 0.35)
    const sync = () => {
      clearInterval(id); id = 0
      if (visible && !document.hidden) id = setInterval(tick, 1000 / DITHER_FPS)
    }
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; sync() })
    io.observe(wrap.current)
    document.addEventListener('visibilitychange', sync)
    return () => { clearInterval(id); io.disconnect(); document.removeEventListener('visibilitychange', sync) }
  }, [reduce])
  return (
    <div ref={wrap} className="size-full">
      <Dithering
        className="size-full opacity-60"
        colorBack="#050505"
        colorFront="#3a2400"
        shape="wave"
        type="4x4"
        size={2}
        scale={1.4}
        speed={0}
        frame={frame}
        minPixelRatio={1}
        maxPixelCount={360000}
      />
    </div>
  )
}
const HEADLINE = ['A familiar voice.', 'An unfamiliar', 'intention.']

// Real scores from the team test set (a genuine recording and its zero-shot clone).
const READOUT = {
  human: { word: 'Human', score: '0.046', note: 'measured on a team member’s real voice', tone: 'text-success' },
  clone: { word: 'Synthetic', score: '0.998', note: 'measured on that same voice, cloned', tone: 'text-danger' },
}

export default function Hero({ revealed, entrancePlaying }) {
  const reduce = useReducedMotion()
  const bars = useRef(null)
  const section = useRef(null)
  const [side, setSide] = useState(null)
  const [touched, setTouched] = useState(false)
  useEffect(() => {
    const on = () => setTouched(true)
    window.addEventListener('pointermove', on, { once: true })
    return () => window.removeEventListener('pointermove', on)
  }, [])
  // Touch: the meter is steered by the thumb or by tilting the phone, and crossing
  // from the human half into the clone half gives a small haptic knock.
  const [touch] = useState(isTouch)
  const steeredAt = useRef(0)
  const tiltOn = useRef(false)
  const onSide = useCallback(s => {
    setSide(s)
    const steering = tiltOn.current || performance.now() - steeredAt.current < 700
    if (steering && s) haptic(s === 'clone' ? [6, 45, 12] : 8)
  }, [])
  const [tilt, toggleTilt] = useTilt((x, y) => bars.current?.steer(x, y))
  useEffect(() => { tiltOn.current = tilt === 'on' }, [tilt])
  const meter = useRef(null)
  const steerFromTouch = e => {
    if (e.pointerType === 'mouse' || !meter.current) return
    const rect = meter.current.getBoundingClientRect()
    steeredAt.current = performance.now()
    bars.current?.steer((e.clientX - rect.left) / rect.width, (e.clientY - rect.top) / rect.height)
  }

  // Entrance: hold the bars flat under the title card, then let them rise.
  useEffect(() => { if (entrancePlaying) bars.current?.flatten() }, [entrancePlaying])
  useEffect(() => { if (revealed) bars.current?.rise(entrancePlaying ? 1100 : 1) }, [revealed, entrancePlaying])

  // Depth: the three planes drift apart at different rates as the hero leaves.
  // Progress is derived from window scroll, not a target measurement: a target
  // measured before the lazy page has height reports 1 and hides the hero until
  // the first scroll.
  const { scrollY } = useScroll()
  const scrollYProgress = useTransform(scrollY, v => {
    const h = section.current?.offsetHeight || window.innerHeight
    return Math.min(1, Math.max(0, v / h))
  })
  const bgY = useTransform(scrollYProgress, [0, 1], ['0%', '18%'])
  const barsY = useTransform(scrollYProgress, [0, 1], ['0%', '9%'])
  const copyY = useTransform(scrollYProgress, [0, 1], ['0%', '-14%'])
  const copyFade = useTransform(scrollYProgress, [0, 0.7], [1, 0])
  const barsFade = useTransform(scrollYProgress, [0.45, 0.95], [1, 0])

  const r = side ? READOUT[side] : null
  const show = revealed

  return (
    <section ref={section} className="relative isolate flex min-h-[100svh] flex-col overflow-hidden" aria-labelledby="hero-title">
      {/* Plane 1: a faint dithered wave, the room the voice is in. */}
      <motion.div style={reduce ? undefined : { y: bgY }} className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[78%] [mask-image:linear-gradient(to_bottom,black_10%,transparent_92%)]" aria-hidden="true">
        <DitherWave reduce={reduce} />
      </motion.div>

      {/* Plane 3: the copy, anchored to the leading edge. */}
      <motion.div style={reduce ? undefined : { y: copyY, opacity: copyFade }} className="relative z-10 mx-auto w-full max-w-[1240px] px-6 pt-[12svh] max-sm:pb-[5.5rem] sm:px-8 sm:pt-[18svh]">
        <h1 id="hero-title" className="max-w-[13ch] text-[clamp(2.75rem,7.4vw,6.75rem)] font-display font-normal leading-[0.95] tracking-[0.005em]">
          {HEADLINE.map((line, i) => (
            <span key={line} className="block overflow-hidden pb-[0.06em]">
              <motion.span
                className={`block ${i === 2 ? 'text-accent' : ''}`}
                initial={reduce ? { opacity: 0 } : { y: '105%' }}
                animate={show ? (reduce ? { opacity: 1 } : { y: '0%' }) : undefined}
                transition={{ duration: 1, ease: EASE, delay: 0.15 + i * 0.09 }}
              >
                {line}
              </motion.span>
            </span>
          ))}
        </h1>
        <motion.div
          className="mt-6 flex max-w-xl flex-col gap-6 sm:mt-8 sm:gap-8"
          initial={{ opacity: 0, y: reduce ? 0 : 16 }}
          animate={show ? { opacity: 1, y: 0 } : undefined}
          transition={{ duration: 0.8, ease: EASE, delay: 0.55 }}
        >
          <p className="text-base leading-relaxed text-muted sm:text-xl">
            {touch ? 'Drag across the meter below, or tilt your phone.' : 'Move across the meter below.'}{' '}
            The left half is a person, the right half is a clone.
            VoiceGuard hears the difference, in English and four Indian languages.
          </p>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
            <Cta href="#demo">Try a sample call</Cta>
            <Cta to="/dashboard" variant="quiet">Analyze your own audio</Cta>
          </div>
        </motion.div>
      </motion.div>

      {/* Plane 2: the meter sits on a frosted glass instrument panel. An amber bloom
          behind the panel bleeds through the frost; the bars stay crisp on top. */}
      <motion.div style={reduce ? undefined : { y: barsY, opacity: barsFade }} className="relative mt-auto h-[38svh] min-h-[240px] w-full sm:h-[46svh] sm:min-h-[260px]">
        <div className="pointer-events-none absolute inset-x-0 bottom-0 top-[6%] mx-auto max-w-[1600px] px-3 sm:px-6" aria-hidden="true">
          <div className="absolute inset-x-[8%] bottom-[-30%] top-[10%] rounded-[50%] bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--accent)_38%,transparent),transparent)] blur-3xl" />
          <div className="hero-glass absolute inset-x-3 bottom-[-1.5rem] top-[12%] rounded-t-[2rem] sm:inset-x-6" />
        </div>
        <div ref={meter} className="pointer-events-none absolute inset-x-0 bottom-0 top-[6%] mx-auto max-w-[1600px] px-6 sm:px-12">
          {touch && (
            // A drag surface over the meter. pan-y keeps vertical swipes scrolling the page;
            // sideways drags steer the bell.
            <div
              data-touch-surface
              aria-hidden="true"
              className="pointer-events-auto absolute inset-0 touch-pan-y"
              onPointerDown={steerFromTouch}
              onPointerMove={steerFromTouch}
            />
          )}
          <VoiceBars ref={bars} onSide={onSide} ariaLabel="Voice meter. The left half moves like a human voice, the right half like a cloned one." />
          <span className="absolute bottom-0 left-1/2 top-[8%] w-px -translate-x-1/2 bg-[repeating-linear-gradient(to_bottom,var(--separator)_0_6px,transparent_6px_12px)]" aria-hidden="true" />
          <span className="label-mono absolute bottom-3 left-8 sm:left-16">Human</span>
          <span className="label-mono absolute bottom-3 right-8 sm:right-16">Clone</span>
        </div>
        {touch && !reduce && (
          <motion.button
            type="button"
            onClick={toggleTilt}
            disabled={tilt === 'unavailable' || tilt === 'denied'}
            aria-pressed={tilt === 'on'}
            className="tilt-chip absolute left-6 top-[-3.5rem] z-10 sm:top-[-3.25rem] inline-flex min-h-9 items-center gap-2 rounded-full border border-hairline bg-ink-1/70 px-3.5 font-mono text-[11px] uppercase tracking-[0.08em] text-muted backdrop-blur-md aria-pressed:border-accent/60 aria-pressed:text-accent disabled:opacity-50"
            initial={{ opacity: 0, y: 8 }}
            animate={show ? { opacity: 1, y: 0 } : undefined}
            transition={{ duration: 0.6, ease: EASE, delay: 1.1 }}
          >
            <span className={`tilt-phone ${tilt === 'off' ? 'is-idle' : ''}`} aria-hidden="true" />
            {{ off: 'Tilt to steer', on: 'Tilt on', unavailable: 'No tilt sensor', denied: 'Tilt blocked' }[tilt]}
          </motion.button>
        )}
        <div className="absolute right-6 top-[-4.75rem] z-10 min-h-[64px] text-right sm:right-10 sm:top-[-5.5rem] sm:min-h-[92px]" aria-live={touched ? 'polite' : 'off'}>
          <AnimatePresence mode="wait">
            {r && (
              <motion.div
                key={side}
                initial={{ opacity: 0, y: reduce ? 0 : 8, filter: 'blur(6px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: reduce ? 0 : -6, filter: 'blur(6px)' }}
                transition={{ duration: 0.28, ease: EASE }}
              >
                <p className={`font-display text-[clamp(1.5rem,3.4vw,2.75rem)] uppercase leading-none ${r.tone}`}>{r.word}</p>
                <p className="mt-1.5 font-mono text-xs text-foreground tabular sm:mt-2 sm:text-sm">spoof score {r.score}</p>
                <p className="mt-1 text-xs text-muted max-sm:hidden">{r.note}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </section>
  )
}
