import { useEffect, useRef, useState } from 'react'
import { motion, useMotionValue, useMotionValueEvent, useReducedMotion, useScroll, useTransform } from 'motion/react'

// Sideways travel reads as breadth: five languages, one rail. Every result is from the
// held-out test; where clones were not measured, the card says so.
const LANGS = [
  { name: 'English', script: 'English', line: 'Sir, your account is blocked. Share the OTP now.', stat: '3.54%', label: 'EER on 3,255 test clips' },
  { name: 'Hindi', script: 'हिन्दी', line: 'तुरंत दस लाख ट्रांसफर करो। किसी को मत बताना।', stat: '0.99%', label: 'EER on 203 test clips' },
  { name: 'Bengali', script: 'বাংলা', line: 'আমি বিপদে আছি, এখনই টাকা পাঠাও।', stat: '0 / 98', label: 'genuine clips wrongly flagged' },
  { name: 'Tamil', script: 'தமிழ்', line: 'நான் சிக்கலில் இருக்கிறேன், உடனே பணம் அனுப்பு.', stat: '1 / 84', label: 'genuine clips wrongly flagged' },
  { name: 'Marathi', script: 'मराठी', line: 'मी अडचणीत आहे, लगेच पैसे पाठव.', stat: '4 / 93', label: 'genuine clips wrongly flagged' },
]

function Card({ lang, progress, index, count }) {
  // Cards settle in sequence as the rail travels, like a drawer being pulled.
  const start = Math.max(0, (index - 0.6) / count)
  const opacity = useTransform(progress, [start, start + 0.12], [index === 0 ? 1 : 0.55, 1])
  const y = useTransform(progress, [start, start + 0.12], [index === 0 ? 0 : 24, 0])
  return (
    <motion.article style={{ opacity, y }} className="flex w-[min(78vw,400px)] shrink-0 snap-start flex-col justify-between gap-12 rounded-3xl border border-border bg-ink-1 p-8">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="font-display text-4xl leading-none text-foreground">{lang.script}</h3>
        <span className="label-mono">{lang.name}</span>
      </div>
      <p className="text-xl leading-snug text-foreground" lang={{ Hindi: 'hi', Bengali: 'bn', Tamil: 'ta', Marathi: 'mr', English: 'en' }[lang.name]}>“{lang.line}”</p>
      <div>
        <p className="font-pixel text-5xl leading-none text-accent">{lang.stat}</p>
        <p className="mt-2 text-sm text-muted">{lang.label}</p>
      </div>
    </motion.article>
  )
}

// The pinned rail lives in its own component so useScroll mounts together with the
// element it tracks. (Bound to a ref that wasn't rendered yet, it never updates and
// the section pins without moving.)
function PinnedRail({ heading, note }) {
  const track = useRef(null)
  const rail = useRef(null)
  const [travel, setTravel] = useState(0)
  const { scrollYProgress } = useScroll({ target: track, offset: ['start start', 'end end'] })
  const x = useTransform(scrollYProgress, v => -v * travel)
  const [p, setP] = useState(0)
  useMotionValueEvent(scrollYProgress, 'change', setP)

  // Travel exactly the rail's overflow, so the closing note lands flush. Measured on
  // mount, again after fonts load, and on resize.
  useEffect(() => {
    const measure = () => { if (rail.current) setTravel(Math.max(0, rail.current.scrollWidth - window.innerWidth)) }
    measure()
    document.fonts?.ready.then(measure)
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  return (
    <section ref={track} className="relative" style={{ height: `calc(100svh + ${travel}px)` }} aria-labelledby="langs-title">
      <div className="sticky top-0 flex h-[100svh] items-center overflow-hidden">
        <motion.div ref={rail} style={{ x }} className="flex w-max items-stretch gap-6 pl-[max(2rem,calc((100vw-1240px)/2+2rem))] pr-16">
          {heading}
          {LANGS.map((l, i) => <Card key={l.name} lang={l} progress={scrollYProgress} index={i + 1} count={LANGS.length + 1} />)}
          {note}
        </motion.div>
        <div className="absolute inset-x-6 bottom-10 mx-auto h-px max-w-[1240px] bg-hairline" aria-hidden="true">
          <span className="block h-px origin-left bg-accent" style={{ transform: `scaleX(${p})` }} />
        </div>
      </div>
    </section>
  )
}

export default function LanguagesSection() {
  const reduce = useReducedMotion()
  const [desktop, setDesktop] = useState(false)
  const settled = useMotionValue(1)

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    const update = () => setDesktop(mq.matches)
    update()
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [])

  const heading = (
    <div className="flex w-[min(80vw,380px)] shrink-0 flex-col justify-end gap-6 pr-6">
      <h2 id="langs-title" className="font-display text-[clamp(2.25rem,4.6vw,3.75rem)] leading-[1] tracking-[0.005em]">
        Five languages. <span className="text-muted">One detector.</span>
      </h2>
      <p className="max-w-xs leading-relaxed text-muted">The same scam, the way it actually arrives. Trained on English and Indian-language speech.</p>
    </div>
  )
  const note = (
    <div className="flex w-[min(78vw,340px)] shrink-0 flex-col justify-end gap-4 pl-2">
      <p className="text-lg text-foreground">Cloned speech in Bengali, Tamil and Marathi is not measured yet.</p>
      <p className="text-sm leading-relaxed text-muted">Those clones are generated for the next training run, so their scores here will change.</p>
    </div>
  )

  if (desktop && !reduce) return <PinnedRail heading={heading} note={note} />

  return (
    <section className="relative py-[clamp(5rem,12vh,8rem)]" aria-labelledby="langs-title">
      <div className="flex snap-x snap-mandatory gap-5 overflow-x-auto px-6 pb-6 [scrollbar-width:none] sm:px-8">
        {heading}
        {LANGS.map(l => <Card key={l.name} lang={l} progress={settled} index={0} count={LANGS.length} />)}
        {note}
      </div>
    </section>
  )
}
