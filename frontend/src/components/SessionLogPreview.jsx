import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import './SessionLogPreview.css'

gsap.registerPlugin(ScrollTrigger)

const AUTOPLAY_MS = 4500
const RESUME_AFTER_MS = 5000

const MOCK_ROWS = [
  { time: '1m ago', caller: '+1 (415) 55•-••12', risk: 6 },
  { time: '4m ago', caller: '+91 98••• •••47', risk: 91 },
  { time: '9m ago', caller: '+44 7•••-••••23', risk: 18 },
  { time: '22m ago', caller: '+1 (212) 55•-••88', risk: 44 },
  { time: '1h ago', caller: '+91 98••• •••12', risk: 76 },
]

function verdictFor(risk) {
  if (risk >= 70) return { label: 'High Risk', tone: 'high' }
  if (risk >= 40) return { label: 'Caution', tone: 'caution' }
  return { label: 'Safe', tone: 'safe' }
}

export default function SessionLogPreview() {

  const rows = MOCK_ROWS

  const sectionRef = useRef(null)
  const trackRef = useRef(null)
  const cardRefs = useRef([])
  const indexRef = useRef(0)
  const autoplayId = useRef(null)
  const resumeId = useRef(null)
  const scrollFrame = useRef(null)
  const [activeIndex, setActiveIndex] = useState(0)

  // IMPORTANT: reset the refs array every render so GSAP never targets
  // stale/duplicate nodes from a previous render pass.
 

  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const getStep = () => {
    const [a, b] = cardRefs.current
    if (a && b) return b.offsetLeft - a.offsetLeft
    return a ? a.offsetWidth + 16 : 0
  }

  const scrollToIndex = (i) => {
  const track = trackRef.current
  const card = cardRefs.current[i]
  if (!track || !card) return
  indexRef.current = i
  setActiveIndex(i)
  track.scrollTo({ left: card.offsetLeft, behavior: reducedMotion ? 'auto' : 'smooth' })
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

  const goTo = (i) => {
    handleInteraction()
    scrollToIndex((i + rows.length) % rows.length)
  }

  // Sync activeIndex/dots when user drags the track manually
  useEffect(() => {
    const track = trackRef.current
    if (!track) return

    const handleScroll = () => {
      if (scrollFrame.current) return
      scrollFrame.current = requestAnimationFrame(() => {
        scrollFrame.current = null
        const step = getStep()
        if (!step) return
        const idx = Math.max(0, Math.min(rows.length - 1, Math.round(track.scrollLeft / step)))
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

  // Entrance reveal + autoplay lifecycle
  useEffect(() => {
  const section = sectionRef.current
  cardRefs.current.length = rows.length
  const cards = cardRefs.current.filter(Boolean)
  if (!section || !cards.length) return

    const ctx = gsap.context(() => {
      gsap.set(cards, { autoAlpha: 0, y: 16 })
      gsap.to(cards, {
        autoAlpha: 1,
        y: 0,
        duration: 0.6,
        stagger: 0.08,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 75%',
          toggleActions: 'play none none none',
          onEnter: startAutoplay,
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
        <h2>Recent calls</h2>
        <p>A live feed of analyzed sessions, verdicts assigned in real time.</p>
      </div>

      <div className="log-carousel">
        <button type="button" className="log-nav" aria-label="Previous call" onClick={() => goTo(activeIndex - 1)}>
          ‹
        </button>

        <div
          className="log-carousel-track"
          ref={trackRef}
          role="region"
          aria-roledescription="carousel"
          aria-label="Call log"
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
                ref={(el) => {
  cardRefs.current[i] = el
}}
              >
                <div className="log-card-top">
                  <span className="log-time">{row.time}</span>
                  <span className={`log-badge log-badge--${verdict.tone}`}>{verdict.label}</span>
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

        <button type="button" className="log-nav" aria-label="Next call" onClick={() => goTo(activeIndex + 1)}>
          ›
        </button>
      </div>

      <div className="log-dots" role="tablist" aria-label="Call log slides">
        {rows.map((row, i) => (
          <button
            key={row.caller + row.time}
            type="button"
            role="tab"
            className={`log-dot${i === activeIndex ? ' log-dot--active' : ''}`}
            aria-label={`Go to call ${i + 1}`}
            aria-selected={i === activeIndex}
            onClick={() => goTo(i)}
          />
        ))}
      </div>
    </section>
  )
}