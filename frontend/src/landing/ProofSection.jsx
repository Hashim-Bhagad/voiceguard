import { useRef } from 'react'
import { useInView } from 'motion/react'
import NumberFlow from '@number-flow/react'
import { MaskLines, ScaleIn } from './Reveal'
import Cta from './Cta'

// Every number here comes from the held-out test or the team's own recordings.
function Count({ value, format, className = '' }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, amount: 0.6 })
  const v = inView ? value : 0
  return (
    <span ref={ref} className={className}>
      <NumberFlow value={v} format={format} transformTiming={{ duration: 1400, easing: 'cubic-bezier(.16,1,.3,1)' }} />
    </span>
  )
}

const SMALL = [
  { value: 0.996, format: { maximumFractionDigits: 3, minimumFractionDigits: 3 }, label: 'ROC-AUC', note: 'how cleanly it ranks clones above real voices' },
  { value: 16, suffix: ' / 16', format: { maximumFractionDigits: 0 }, label: 'Real clones caught', note: 'zero-shot clones of five team members' },
  { value: 0.0099, format: { style: 'percent', maximumFractionDigits: 2 }, label: 'Hindi EER', note: 'on 203 held-out Hindi clips' },
  { value: 0, suffix: ' / 378', format: { maximumFractionDigits: 0 }, label: 'Unseen-TTS clones missed', note: 'from three systems it never trained on' },
]

export default function ProofSection() {
  return (
    <section id="proof" className="relative px-6 py-[clamp(6rem,16vh,10rem)] sm:px-8" aria-labelledby="proof-title">
      <div className="mx-auto max-w-[1240px]">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-end">
          <div>
            <MaskLines as="h2" className="text-[clamp(2.25rem,4.6vw,3.75rem)] font-display font-normal leading-[1] tracking-[0.005em]">
              <span id="proof-title">Measured, not promised.</span>
            </MaskLines>
            <ScaleIn delay={0.1} className="mt-12">
              <p className="font-pixel text-[clamp(6rem,17vw,13rem)] leading-[0.85] text-accent">
                <Count value={0.0297} format={{ style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 }} />
              </p>
              <p className="mt-6 max-w-lg text-lg text-foreground">Equal error rate on 3,733 held-out clips from speakers the model never heard, in five languages.</p>
            </ScaleIn>
          </div>
          <ScaleIn delay={0.2} className="lg:pb-4">
            <p className="leading-relaxed text-muted">
              At the threshold we use, it catches nearly every clone but also flags 13.8% of genuine clips,
              mostly noisy recordings. That is why a flag starts a liveness check instead of blocking the call.
            </p>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3">
              <Cta href="https://huggingface.co/Hashim-Bhagad/voiceguard-xlsr-aasist-indic" variant="quiet" external>Model card</Cta>
              <Cta href="https://github.com/Hashim-Bhagad/voiceguard" variant="quiet" external>Source code</Cta>
            </div>
          </ScaleIn>
        </div>
        <dl className="mt-20 grid gap-px overflow-hidden rounded-3xl border border-border bg-hairline sm:grid-cols-2 lg:grid-cols-4">
          {SMALL.map((s, i) => (
            <ScaleIn key={s.label} delay={i * 0.06} className="flex flex-col gap-3 bg-background p-7">
              <dt className="label-mono">{s.label}</dt>
              <dd className="font-pixel text-5xl leading-none text-foreground">
                <Count value={s.value} format={s.format} />
                {s.suffix && <span className="text-muted">{s.suffix}</span>}
              </dd>
              <dd className="text-sm text-muted">{s.note}</dd>
            </ScaleIn>
          ))}
        </dl>
      </div>
    </section>
  )
}
