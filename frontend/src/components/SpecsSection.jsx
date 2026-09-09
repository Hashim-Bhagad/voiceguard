import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import PhoneMockup from './PhoneMockup'
import './SpecsSection.css'

gsap.registerPlugin(ScrollTrigger)

const SPECS = [
  {
    title: 'Real-time detection',
    body: 'Every signal is scored while the call is still happening — not minutes later in a fraud review queue.',
  },
  {
    title: 'Multilingual, accent-aware',
    body: "Models are trained across languages and accents, so accuracy doesn't drop for callers who don't sound like the training set.",
  },
  {
    title: 'No raw audio stored',
    body: 'VoiceGuard scores the call and discards the audio — only the risk signals and flagged transcript excerpts are retained.',
  },
  {
    title: 'API-first, integration-ready',
    body: 'Drop into your existing stack — SIP trunk, contact-center platform, or softphone — through a single real-time API.',
  },
]

// Unlike FeatureExplainer's sequence, these are parallel selling points, not
// steps — so each item reveals once and stays (a checklist assembling)
// rather than crossfading out for the next.
function itemVisual(progress, index, total) {
  const threshold = index / total
  const fade = 0.7 / total
  const t = gsap.utils.clamp(0, 1, (progress - threshold) / fade)
  return { opacity: t, y: 18 * (1 - t), dash: 12 * (1 - t) }
}

export default function SpecsSection() {
  const sectionRef = useRef(null)
  const pinRef = useRef(null)
  const phoneRef = useRef(null)
  const itemRefs = useRef([])
  const checkRefs = useRef([])

  useEffect(() => {
    const section = sectionRef.current
    const pinEl = pinRef.current
    const phone = phoneRef.current
    if (!section || !pinEl || !phone) return

    const ctx = gsap.context(() => {
      const applyProgress = (progress) => {
        gsap.set(phone, {
          rotateY: gsap.utils.interpolate(-4, 4, progress),
          rotateX: gsap.utils.interpolate(2, -2, progress),
        })

        itemRefs.current.forEach((el, i) => {
          if (!el) return
          const { opacity, y, dash } = itemVisual(progress, i, SPECS.length)
          gsap.set(el, { opacity, y })
          const check = checkRefs.current[i]
          check && gsap.set(check, { strokeDashoffset: dash })
        })
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
    <section className="specs-section" ref={sectionRef}>
      <div className="specs-pin" ref={pinRef}>
        <div className="specs-copy">
          <h2 className="specs-heading">Built to run quietly in the background.</h2>

          <ul className="specs-list">
            {SPECS.map((spec, i) => (
              <li
                key={spec.title}
                className="specs-item"
                ref={(el) => (itemRefs.current[i] = el)}
              >
                <svg className="specs-check" viewBox="0 0 20 20" aria-hidden="true">
                  <circle cx="10" cy="10" r="9" />
                  <path
                    d="M6 10.5l2.5 2.5L14 7.5"
                    ref={(el) => (checkRefs.current[i] = el)}
                  />
                </svg>
                <div>
                  <h3>{spec.title}</h3>
                  <p>{spec.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <PhoneMockup ref={phoneRef} state="analyzing">
          <span className="phone-mockup-label">LIVE MONITORING</span>
        </PhoneMockup>
      </div>
    </section>
  )
}
