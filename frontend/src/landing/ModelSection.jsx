import { useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useScroll } from 'motion/react'
import { MaskLines, BlurIn } from './Reveal'

const EASE = [0.16, 1, 0.3, 1]

const STEPS = [
  {
    kicker: '4.04 seconds',
    title: 'It starts as a waveform.',
    body: '64,600 raw samples at 16 kHz. No transcript, no features chosen by hand: the model reads the sound itself.',
  },
  {
    kicker: 'XLS-R 300M',
    title: 'A model that has heard 128 languages.',
    body: 'Meta’s XLS-R was pre-trained on 436,000 hours of speech. We fine-tuned its top 8 of 24 layers, 101M of its 316M parameters, so it learns what cloned speech gets wrong.',
  },
  {
    kicker: 'AASIST',
    title: 'A graph that hunts for artefacts.',
    body: 'Frequency bands and moments in time become two graphs. Attention links the suspicious ones: the odd high band, the transition that is too smooth.',
  },
  {
    kicker: 'One number',
    title: 'Then it commits to a score.',
    body: 'Above the threshold, the caller gets a liveness check. Below it, the call goes on. Every score shows the evidence behind it.',
  },
]

function Waveform() {
  return (
    <svg viewBox="0 0 400 160" className="h-full w-full" aria-hidden="true">
      {Array.from({ length: 96 }, (_, i) => {
        const a = Math.abs(Math.sin(i * 0.37) * Math.cos(i * 0.11)) * 60 + 6
        return <motion.rect key={i} x={i * 4.15} width="2.2" rx="1.1" fill="var(--accent)" initial={{ y: 80, height: 0, opacity: 0.2 }} animate={{ y: 80 - a, height: a * 2, opacity: 0.35 + a / 120 }} transition={{ duration: 0.8, ease: EASE, delay: i * 0.006 }} />
      })}
    </svg>
  )
}

function Layers() {
  return (
    <div className="flex h-full flex-col-reverse justify-center gap-[5px] px-8" aria-hidden="true">
      {Array.from({ length: 24 }, (_, i) => {
        const tuned = i >= 16
        return (
          <motion.div key={i} className="flex items-center gap-3" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, ease: EASE, delay: i * 0.025 }}>
            <span className="w-5 text-right font-mono text-[10px] text-muted tabular">{i}</span>
            <span className={`h-[7px] flex-1 rounded-sm ${tuned ? 'bg-accent' : 'bg-ink-3'}`} />
          </motion.div>
        )
      })}
      <p className="label-mono mb-3 flex justify-between"><span>Frozen 0 to 15</span><span className="text-accent">Fine-tuned 16 to 23</span></p>
    </div>
  )
}

function Graph() {
  const freq = [[60, 40], [120, 22], [170, 64], [90, 104], [150, 124]]
  const time = [[250, 50], [320, 30], [360, 84], [280, 112], [340, 134]]
  const links = [[2, 0], [4, 3], [2, 2]]
  return (
    <svg viewBox="0 0 400 160" className="h-full w-full" aria-hidden="true">
      {[[0, 1], [1, 2], [0, 3], [3, 4], [2, 4]].map(([a, b], i) => <line key={`f${i}`} x1={freq[a][0]} y1={freq[a][1]} x2={freq[b][0]} y2={freq[b][1]} stroke="var(--separator)" strokeWidth="1.2" />)}
      {[[0, 1], [1, 2], [0, 3], [3, 4], [2, 4]].map(([a, b], i) => <line key={`t${i}`} x1={time[a][0]} y1={time[a][1]} x2={time[b][0]} y2={time[b][1]} stroke="var(--separator)" strokeWidth="1.2" />)}
      {links.map(([a, b], i) => (
        <motion.line key={`l${i}`} x1={freq[a][0]} y1={freq[a][1]} x2={time[b][0]} y2={time[b][1]} stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 4" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9, ease: EASE, delay: 0.3 + i * 0.15 }} />
      ))}
      {freq.map(([x, y], i) => <motion.circle key={`fc${i}`} cx={x} cy={y} r={i === 2 || i === 4 ? 7 : 5} fill="var(--foreground)" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: i * 0.05 }} />)}
      {time.map(([x, y], i) => <motion.circle key={`tc${i}`} cx={x} cy={y} r={i === 0 || i === 3 ? 7 : 5} fill="var(--accent)" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.15 + i * 0.05 }} />)}
      <text x="40" y="152" className="fill-muted font-mono text-[10px]">frequency</text>
      <text x="300" y="16" className="fill-muted font-mono text-[10px]">time</text>
    </svg>
  )
}

function Score() {
  return (
    <div className="flex h-full flex-col items-start justify-center gap-3 px-8" aria-hidden="true">
      <p className="label-mono">Spoof score</p>
      <motion.p className="font-pixel text-[clamp(4rem,8vw,7rem)] leading-none text-danger" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE }}>0.998</motion.p>
      <p className="text-sm text-muted">A team member’s cloned voice, scored by the live model.</p>
    </div>
  )
}

const VISUALS = [Waveform, Layers, Graph, Score]

// Desktop: a sticky stage that changes as the reader scrolls through a tall track.
function Pinned() {
  const track = useRef(null)
  const [step, setStep] = useState(0)
  const { scrollYProgress } = useScroll({ target: track, offset: ['start start', 'end end'] })
  useMotionValueEvent(scrollYProgress, 'change', p => setStep(Math.min(STEPS.length - 1, Math.floor(p * STEPS.length))))
  const Visual = VISUALS[step]
  const s = STEPS[step]
  return (
    <div ref={track} className="relative h-[340vh]">
      <div className="sticky top-0 flex h-[100svh] items-center">
        <div className="mx-auto grid w-full max-w-[1240px] grid-cols-[minmax(0,5fr)_minmax(0,6fr)] items-center gap-20 px-8">
          <div className="flex flex-col gap-10">
            <ol className="flex gap-2" aria-label="Steps">
              {STEPS.map((x, i) => (
                <li key={x.kicker} className="h-[3px] w-12 overflow-hidden rounded-full bg-ink-3">
                  <span className={`block h-full bg-accent transition-transform duration-500 ${i <= step ? 'translate-x-0' : '-translate-x-full'}`} />
                </li>
              ))}
            </ol>
            <div className="min-h-[300px]">
              <AnimatePresence mode="wait">
                <motion.div key={step} initial={{ opacity: 0, y: 20, filter: 'blur(6px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, y: -12, filter: 'blur(6px)' }} transition={{ duration: 0.5, ease: EASE }}>
                  <p className="label-mono text-accent">{s.kicker}</p>
                  <h3 className="mt-4 text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-[1.02] tracking-[-0.03em]">{s.title}</h3>
                  <p className="mt-6 max-w-md text-lg leading-relaxed text-muted">{s.body}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
          <div className="relative aspect-[5/4] w-full overflow-hidden rounded-3xl border border-border bg-ink-1">
            <AnimatePresence mode="wait">
              <motion.div key={step} className="absolute inset-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.35 }}>
                <Visual />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}

// Phones and reduced motion: the same four steps as a plain sequence.
function Stacked() {
  return (
    <ol className="mx-auto flex max-w-[1240px] flex-col gap-16 px-6 sm:px-8">
      {STEPS.map((s, i) => {
        const Visual = VISUALS[i]
        return (
          <BlurIn as="li" key={s.kicker} className="flex flex-col gap-6">
            <div className="relative aspect-[5/4] overflow-hidden rounded-3xl border border-border bg-ink-1"><Visual /></div>
            <div>
              <p className="label-mono text-accent">{s.kicker}</p>
              <h3 className="mt-3 text-2xl font-semibold tracking-[-0.02em]">{s.title}</h3>
              <p className="mt-3 leading-relaxed text-muted">{s.body}</p>
            </div>
          </BlurIn>
        )
      })}
    </ol>
  )
}

export default function ModelSection() {
  const reduce = useReducedMotion()
  return (
    <section id="model" className="relative py-[clamp(6rem,14vh,9rem)]" aria-labelledby="model-title">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-8">
        <MaskLines as="h2" className="max-w-[16ch] text-[clamp(2.25rem,4.6vw,3.75rem)] font-display font-normal leading-[1] tracking-[0.005em]">
          <span id="model-title">How four seconds</span>
          <span className="text-muted">become one number.</span>
        </MaskLines>
      </div>
      <div className="mt-12 lg:mt-0">
        <div className="hidden lg:block">{reduce ? <div className="mt-16"><Stacked /></div> : <Pinned />}</div>
        <div className="lg:hidden"><Stacked /></div>
      </div>
    </section>
  )
}
