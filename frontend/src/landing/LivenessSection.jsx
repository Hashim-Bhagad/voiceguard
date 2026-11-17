import { useRef } from 'react'
import { motion, useReducedMotion, useScroll, useTransform } from 'motion/react'
import { MaskLines, BlurIn } from './Reveal'
import Cta from './Cta'

const DIGITS = ['4', '7', '2', '9']

// An iris that opens with the scroll: a fresh challenge appearing out of the dark.
export default function LivenessSection() {
  const reduce = useReducedMotion()
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'center center'] })
  const radius = useTransform(scrollYProgress, [0, 1], ['0%', '75%'])
  const clip = useTransform(radius, r => `circle(${r} at 50% 50%)`)

  return (
    <section id="liveness" ref={ref} className="relative px-6 py-[clamp(6rem,16vh,10rem)] sm:px-8" aria-labelledby="liveness-title">
      <div className="mx-auto grid max-w-[1240px] items-center gap-16 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="flex flex-col gap-8">
          <MaskLines as="h2" className="text-[clamp(2.25rem,4.6vw,3.75rem)] font-display font-normal leading-[1] tracking-[0.005em]">
            <span id="liveness-title">Unsure?</span>
            <span className="text-muted">Ask for proof.</span>
          </MaskLines>
          <BlurIn delay={0.15} className="flex flex-col gap-6">
            <p className="text-lg leading-relaxed text-muted">
              A score is a risk signal, not an identity check. When a call looks risky, VoiceGuard
              generates four fresh digits that expire in 30 seconds. The caller says them back, and the response is
              checked twice: are the digits right, and does the voice still score as human?
            </p>
            <div><Cta to="/dashboard/challenge" variant="secondary">Try a liveness check</Cta></div>
          </BlurIn>
        </div>
        <motion.div style={reduce ? undefined : { clipPath: clip }} className="relative grid aspect-square place-items-center overflow-hidden rounded-[2rem] border border-border bg-ink-1">
          <div className="flex flex-col items-center gap-6">
            <p className="label-mono">Ask the caller to repeat</p>
            <div className="flex gap-3 sm:gap-4">
              {DIGITS.map(d => (
                <span key={d} className="grid h-24 w-16 place-items-center rounded-2xl border border-border bg-background font-pixel text-5xl text-accent sm:h-32 sm:w-24 sm:text-7xl">{d}</span>
              ))}
            </div>
            <p className="font-mono text-sm text-muted">“four seven two nine”</p>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
