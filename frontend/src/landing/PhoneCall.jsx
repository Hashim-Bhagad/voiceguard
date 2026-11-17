import { useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from 'motion/react'
import { Mic, PhoneOff, ShieldAlert, Volume2 } from 'lucide-react'

const EASE = [0.16, 1, 0.3, 1]

// A small CSS pixel meter for the phone screen: 18 columns of square cells.
function MiniMeter({ live }) {
  return (
    <div className="flex h-14 items-end justify-center gap-[3px]" aria-hidden="true">
      {Array.from({ length: 18 }, (_, i) => (
        <span
          key={i}
          className={`phone-meter-col ${live ? 'is-live' : ''}`}
          style={{ '--d': `${(i % 7) * -0.13}s`, '--h': `${30 + ((i * 37) % 60)}%` }}
        />
      ))}
    </div>
  )
}

/*
  The call plays out as the section scrolls past: it rings, it connects and the
  voice meter runs, then VoiceGuard drops its warning. Purely illustrative: no
  score is shown, because no recording was scored.
*/
export default function PhoneCall() {
  const ref = useRef(null)
  const [stage, setStage] = useState(0) // 0 ringing, 1 connected, 2 flagged
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.8', 'end 0.35'] })
  useMotionValueEvent(scrollYProgress, 'change', p => setStage(p < 0.3 ? 0 : p < 0.62 ? 1 : 2))

  return (
    <div ref={ref} className="relative mx-auto w-[min(300px,78vw)]">
      <div className="absolute -inset-10 -z-10 rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--accent)_16%,transparent),transparent)] blur-2xl" aria-hidden="true" />
      <div className="relative aspect-[9/19] rounded-[3rem] border border-[color-mix(in_oklab,var(--white)_12%,transparent)] bg-ink-1 p-2.5 shadow-[0_40px_80px_-30px_oklch(0_0_0/0.9)]">
        <div className="relative flex h-full flex-col overflow-hidden rounded-[2.4rem] bg-[linear-gradient(to_bottom,var(--ink-2),var(--ink-0)_70%)] px-6 pb-8 pt-14">
          <span className="absolute left-1/2 top-3 h-6 w-24 -translate-x-1/2 rounded-full bg-black" aria-hidden="true" />

          <AnimatePresence>
            {stage === 2 && (
              <motion.div
                className="glass absolute inset-x-3 top-12 z-10 flex items-start gap-3 rounded-2xl p-3.5"
                initial={{ opacity: 0, y: -24, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.5, ease: EASE }}
                role="status"
              >
                <ShieldAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden="true" />
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-foreground">Likely a cloned voice</p>
                  <p className="mt-0.5 text-[12px] leading-snug text-muted">VoiceGuard suggests you verify before sending money.</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex flex-col items-center gap-3 text-center">
            <p className="label-mono">{stage === 0 ? 'Incoming call' : 'Call in progress'}</p>
            <span className="grid size-20 place-items-center rounded-full border border-border bg-ink-3 text-2xl font-semibold text-foreground">P</span>
            <p className="text-2xl font-semibold tracking-[-0.02em] text-foreground">Papa</p>
            <p className="font-mono text-sm text-muted tabular">{stage === 0 ? 'mobile' : stage === 1 ? '00:12' : '00:31'}</p>
          </div>

          <div className="mt-auto flex flex-col gap-10">
            <MiniMeter live={stage > 0} />
            {stage === 0 ? (
              <div className="flex justify-between px-4" aria-hidden="true">
                <span className="grid size-14 place-items-center rounded-full bg-danger text-danger-foreground"><PhoneOff className="size-6" /></span>
                <span className="grid size-14 place-items-center rounded-full bg-success text-success-foreground"><Volume2 className="size-6" /></span>
              </div>
            ) : (
              <div className="flex justify-between px-4" aria-hidden="true">
                <span className="grid size-14 place-items-center rounded-full bg-ink-3 text-foreground"><Mic className="size-6" /></span>
                <span className="grid size-14 place-items-center rounded-full bg-danger text-danger-foreground"><PhoneOff className="size-6" /></span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
