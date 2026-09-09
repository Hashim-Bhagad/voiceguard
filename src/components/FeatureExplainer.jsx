import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import PhoneMockup from './PhoneMockup'
import './FeatureExplainer.css'

gsap.registerPlugin(ScrollTrigger)

const STATES = [
  {
    label: '1. Acoustic Analysis',
    side: 'left',
    heading: 'Every call gets an acoustic score.',
    body: 'A dedicated anti-spoofing model listens to the raw audio itself — the micro-artifacts synthetic voices leave behind — and scores how likely it is to be machine-generated.',
  },
  {
    label: '2. Linguistic Analysis',
    side: 'right',
    heading: 'The words get read too.',
    body: 'A live transcript is scanned in parallel for the pressure tactics fraud calls rely on — urgency, authority, secrecy — the language that precedes a costly mistake.',
  },
  {
    label: '3. Risk Fusion',
    side: 'left',
    heading: 'Two signals, one score.',
    body: "Acoustic and linguistic risk fuse into a single real-time score, so a call isn't flagged on a hunch from one signal alone — both have to agree something's wrong.",
  },
  {
    label: '4. Challenge Response',
    side: 'right',
    heading: 'One live question breaks the clone.',
    body: "When risk crosses the line, VoiceGuard asks the caller to repeat back a random phrase or number on the spot. Pre-rendered clones can't produce it convincingly in real time.",
  },
]

const SLIDE = 24

// Each state owns an even slice of scroll progress, with a soft crossfade
// at the edges so adjacent states hand off smoothly instead of snapping.
function stateVisual(progress, index, total) {
  const size = 1 / total
  const start = index * size
  const end = start + size
  const fade = size * 0.3

  if (progress <= start - fade) return { opacity: 0, y: SLIDE }
  if (progress >= end + fade) return { opacity: 0, y: -SLIDE }
  if (progress < start + fade) {
    const t = (progress - (start - fade)) / (fade * 2)
    return { opacity: t, y: SLIDE * (1 - t) }
  }
  if (progress > end - fade) {
    const t = (progress - (end - fade)) / (fade * 2)
    return { opacity: 1 - t, y: -SLIDE * t }
  }
  return { opacity: 1, y: 0 }
}

export default function FeatureExplainer() {
  const sectionRef = useRef(null)
  const pinRef = useRef(null)
  const phoneRef = useRef(null)
  const blockRefs = useRef([])
  const lastIndex = useRef(0)
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    const section = sectionRef.current
    const pinEl = pinRef.current
    const phone = phoneRef.current
    if (!section || !pinEl || !phone) return

    const ctx = gsap.context(() => {
      const applyProgress = (progress) => {
        gsap.set(phone, {
          rotateY: gsap.utils.interpolate(-12, 12, progress),
          rotateX: gsap.utils.interpolate(5, -5, progress),
        })

        blockRefs.current.forEach((el, i) => {
          if (!el) return
          const { opacity, y } = stateVisual(progress, i, STATES.length)
          gsap.set(el, { opacity, y })
        })

        const idx = Math.min(
          STATES.length - 1,
          Math.floor(progress * STATES.length),
        )
        if (idx !== lastIndex.current) {
          lastIndex.current = idx
          setActiveIndex(idx)
        }
      }

      const trigger = ScrollTrigger.create({
        trigger: section,
        start: 'top top',
        end: 'bottom bottom',
        pin: pinEl,
        onUpdate: (self) => applyProgress(self.progress),
      })

      applyProgress(trigger.progress)
    }, section)

    document.fonts?.ready.then(() => ScrollTrigger.refresh())

    return () => ctx.revert()
  }, [])

  return (
    <section className="feature-explainer" ref={sectionRef}>
      <div className="feature-pin" ref={pinRef}>
        <div className="feature-slot feature-slot--left">
          {STATES.map((s, i) =>
            s.side === 'left' ? (
              <div
                key={s.label}
                className="feature-block"
                ref={(el) => (blockRefs.current[i] = el)}
              >
                <h3>{s.heading}</h3>
                <p>{s.body}</p>
              </div>
            ) : null,
          )}
        </div>

        <PhoneMockup ref={phoneRef} state="analyzing">
          <span key={activeIndex} className="phone-mockup-label">
            {STATES[activeIndex].label}
          </span>
        </PhoneMockup>

        <div className="feature-slot feature-slot--right">
          {STATES.map((s, i) =>
            s.side === 'right' ? (
              <div
                key={s.label}
                className="feature-block"
                ref={(el) => (blockRefs.current[i] = el)}
              >
                <h3>{s.heading}</h3>
                <p>{s.body}</p>
              </div>
            ) : null,
          )}
        </div>
      </div>
    </section>
  )
}
