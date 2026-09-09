import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import './ProblemSection.css'

gsap.registerPlugin(ScrollTrigger)

export default function ProblemSection({ onEnter, onLeaveBack }) {
  const sectionRef = useRef(null)
  const copyRef = useRef(null)

  useEffect(() => {
    const section = sectionRef.current
    const copy = copyRef.current
    if (!section || !copy) return

    const ctx = gsap.context(() => {
      gsap.from(copy, {
        y: 40,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 75%',
          toggleActions: 'play none none none',
        },
      })

      ScrollTrigger.create({
        trigger: section,
        start: 'top 60%',
        end: 'bottom 40%',
        onEnter: () => onEnter?.(),
        onEnterBack: () => onEnter?.(),
        onLeave: () => onLeaveBack?.(),
        onLeaveBack: () => onLeaveBack?.(),
      })
    }, section)

    // Space Grotesk loads async and can reflow Hero's headline height,
    // which shifts where this section starts — resync once fonts settle.
    document.fonts?.ready.then(() => ScrollTrigger.refresh())

    return () => ctx.revert()
  }, [onEnter, onLeaveBack])

  return (
    <section className="problem-section" ref={sectionRef}>
      <div className="problem-copy" ref={copyRef}>
        <h2 className="problem-heading">
          Your CEO&rsquo;s voice can be faked in seconds.
        </h2>
        <p className="problem-body">
          Generative voice models can clone an executive&rsquo;s voice from a
          few seconds of public audio — an earnings call, a podcast, a
          keynote. Fraudsters use the clone to call finance teams and push
          through urgent wire transfers, and the voice sounds exactly right.
          VoiceGuard listens for the signs a human ear misses.
        </p>
      </div>
    </section>
  )
}
