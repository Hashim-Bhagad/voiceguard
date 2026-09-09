import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useAnalysis } from '../lib/useAnalysis'
import './SessionLogPreview.css'

gsap.registerPlugin(ScrollTrigger)

// useAnalysis() only returns one current-session result (no caller id,
// timestamp, or history — see src/lib/useAnalysis.js), so it can only
// supply the top "Just now" card's risk score. The rest of the log is
// realistic static mock data standing in for a future session-history
// endpoint, spanning all three verdict bands for a representative preview.
const MOCK_ROWS = [
  { time: '2m ago', caller: '+1 (415) •••-2291', risk: 6 },
  { time: '9m ago', caller: '+1 (212) •••-7734', risk: 91 },
  { time: '24m ago', caller: '+44 20 ••••-5521', risk: 18 },
  { time: '41m ago', caller: '+1 (917) •••-8823', risk: 44 },
  { time: '1h ago', caller: '+91 98••• •••12', risk: 76 },
]

const AUTOPLAY_MS = 3500
const RESUME_AFTER_MS = 5000

function verdictFor(risk) {
  if (risk >= 67) return { label: 'High Risk', tone: 'high' }
  if (risk >= 34) return { label: 'Caution', tone: 'caution' }
  return { label: 'Safe', tone: 'safe' }
}

export default function SessionLogPreview() {
  const { final_risk_score } = useAnalysis()

  const rows = [
    {
      time: 'Just now',
      caller: '+1 (628) •••-0447',
      risk: Math.round(final_risk_score * 100),
    },
    ...MOCK_ROWS,
  ]

  const sectionRef = useRef(null)
  const trackRef = useRef(null)
  const cardRefs = useRef([])
  const indexRef = useRef(0)
  const autoplayId = useRef(null)
  const resumeId = useRef(null)
  const scrollFrame = useRef(null)
  const [activeIndex, setActiveIndex] = useState(0)

  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const getStep = () => {
    const [a, b] = cardRefs.current
    if (a && b) return b.offsetLeft - a.offsetLeft
    return a ? a.offsetWidth + 16 : 0
  }

  const scrollToIndex = (index) => {
    const track = trackRef.current
    const card = cardRefs.current[index]
    if (!track || !card) return
    track.scrollTo({ left: card.offsetLeft, behavior: 'smooth' })
  }

  const stopAutoplay = () => {
    if (autoplayId.current) clearInterval(autoplayId.current)
    autoplayId.current = null
  }

  const startAutoplay = () => {
    stopAutoplay()
    if (reducedMotion) return
    autoplayId.current = setInterval(() => {
      scrollToIndex((indexRef.current + 1) % rows.length)
    }, AUTOPLAY_MS)
  }

  const handleInteraction = () => {
    stopAutoplay()
    if (resumeId.current) clearTimeout(resumeId.current)
    resumeId.current = setTimeout(startAutoplay, RESUME_AFTER_MS)
  }

  const goTo = (index) => {
    handleInteraction()
    scrollToIndex((index + rows.length) % rows.length)
  }

  useEffect(() => {
    const track = trackRef.current
    if (!track) return

    const handleScroll = () => {
      if (scrollFrame.current) return
      scrollFrame.current = requestAnimationFrame(() => {
        scrollFrame.current = null
        const step = getStep()
        if (!step) return
        const idx = Math.max(
          0,
          Math.min(rows.length - 1, Math.round(track.scrollLeft / step)),
        )
        indexRef.current = idx
        setActiveIndex((prev) => (prev === idx ? prev : idx))
      })
    }

    track.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      track.removeEventListener('scroll', handleScroll)
      if (scrollFrame.current) cancelAnimationFrame(scrollFrame.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const section = sectionRef.current
    const cards = cardRefs.current.filter(Boolean)
    if (!section || !cards.length) return

    const ctx = gsap.context(() => {
      gsap.from(cards, {
        opacity: 0,
        y: 16,
        duration: 0.5,
        ease: 'power2.out',
        stagger: 0.08,
        scrollTrigger: {
          trigger: section,
          start: 'top 75%',
          toggleActions: 'play none none none',
          onEnter: startAutoplay,
          onEnterBack: startAutoplay,
          onLeave: stopAutoplay,
          onLeaveBack: stopAutoplay,
        },
      })
    }, section)

    return () => {
      ctx.revert()
      stopAutoplay()
      if (resumeId.current) clearTimeout(resumeId.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <section className="log-section" ref={sectionRef}>
      <div className="log-intro">
        <h2 className="log-heading">Every call, logged and scored.</h2>
        <p className="log-sub">
          A live record of what's been screened — nothing stored beyond the
          score.
        </p>
      </div>

      <div className="log-carousel">
        <button
          type="button"
          className="log-nav log-nav--prev"
          aria-label="Previous call"
          onClick={() => goTo(activeIndex - 1)}
        >
          ‹
        </button>

        <div
          className="log-carousel-track"
          ref={trackRef}
          role="region"
          aria-roledescription="carousel"
          aria-label="Recent call log"
          tabIndex={0}
          onPointerDown={handleInteraction}
          onWheel={handleInteraction}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') goTo(activeIndex + 1)
            if (e.key === 'ArrowLeft') goTo(activeIndex - 1)
          }}
        >
          {rows.map((row, i) => {
            const verdict = verdictFor(row.risk)
            return (
              <div
                className="log-card"
                key={row.caller + row.time}
                ref={(el) => (cardRefs.current[i] = el)}
              >
                <div className="log-card-top">
                  <span className="log-time">{row.time}</span>
                  <span className={`log-badge log-badge--${verdict.tone}`}>
                    {verdict.label}
                  </span>
                </div>

                <div className="log-caller">{row.caller}</div>

                <div className="log-risk">
                  <span className="log-risk-track">
                    <span
                      className={`log-risk-fill log-risk-fill--${verdict.tone}`}
                      style={{ width: `${row.risk}%` }}
                    />
                  </span>
                  {row.risk}%
                </div>
              </div>
            )
          })}
        </div>

        <button
          type="button"
          className="log-nav log-nav--next"
          aria-label="Next call"
          onClick={() => goTo(activeIndex + 1)}
        >
          ›
        </button>
      </div>

      <div className="log-dots" role="tablist" aria-label="Call log slides">
        {rows.map((row, i) => (
          <button
            type="button"
            key={row.caller + row.time}
            className={`log-dot${i === activeIndex ? ' log-dot--active' : ''}`}
            role="tab"
            aria-label={`Go to call ${i + 1}`}
            aria-selected={i === activeIndex}
            onClick={() => goTo(i)}
          />
        ))}
      </div>
    </section>
  )
}
