import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { SplitText } from 'gsap/SplitText'
import './Hero.css'

gsap.registerPlugin(SplitText)

export default function Hero({ ready }) {
  const headlineRef = useRef(null)
  const revealRef = useRef(null)

  useEffect(() => {
    const el = headlineRef.current
    if (!el) return

    const ctx = gsap.context(() => {
      const split = SplitText.create(el, {
        type: 'chars,words',
        mask: 'chars',
        charsClass: 'hero-char',
        wordsClass: 'hero-word',
      })

      // Hide the characters immediately (while the Loader still covers the
      // screen) but don't play the reveal yet — it waits for `ready`.
      gsap.set(split.chars, { y: 40, opacity: 0 })

      revealRef.current = gsap.to(split.chars, {
        y: 0,
        opacity: 1,
        duration: 0.5,
        ease: 'back.out(1.7)',
        stagger: 0.035,
        paused: true,
      })
    }, el)

    return () => ctx.revert()
  }, [])

  useEffect(() => {
    if (ready) revealRef.current?.play()
  }, [ready])

  return (
    <section className="hero-section" id="hero">
      <div className="hero-copy">
        <h1 className="hero-headline" ref={headlineRef}>
          Stop voice-cloning fraud before it costs you.
        </h1>
        <p className="hero-subhead">
          VoiceGuard analyzes every call in real time and flags cloned voices
          before your team acts on them.
        </p>
        <a className="hero-cta" href="#demo">
          See it in action
        </a>
      </div>
    </section>
  )
}
