import { useCallback, useState } from 'react'
import useLenis from '../landing/useLenis'
import Entrance from '../landing/Entrance'
import Nav from '../landing/Nav'
import Hero from '../landing/Hero'
import CallSection from '../landing/CallSection'
import DemoSection from '../landing/DemoSection'
import ModelSection from '../landing/ModelSection'
import ProofSection from '../landing/ProofSection'
import LivenessSection from '../landing/LivenessSection'
import CloseSection from '../landing/CloseSection'
import AsciiFooter from '../landing/AsciiFooter'
import LanguagesSection from '../landing/LanguagesSection'
import PixelTrail from '../landing/PixelTrail'

export default function Landing() {
  useLenis()
  const [entrancePlaying] = useState(() => document.documentElement.dataset.entrance !== 'done'
    && !window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [revealed, setRevealed] = useState(false)
  const onReveal = useCallback(() => setRevealed(true), [])

  return (
    <div className="grain relative min-h-dvh bg-background text-foreground">
      <Entrance onReveal={onReveal} />
      <PixelTrail />
      <Nav />
      <main id="main-content" tabIndex={-1} className="relative z-[1] focus:outline-none">
        <Hero revealed={revealed} entrancePlaying={entrancePlaying} />
        <CallSection />
        <DemoSection />
        <LanguagesSection />
        <ModelSection />
        <ProofSection />
        <LivenessSection />
        <CloseSection />
      </main>
      <div className="relative z-[1]"><AsciiFooter /></div>
    </div>
  )
}
