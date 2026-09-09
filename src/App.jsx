import { useCallback, useState } from 'react'
import Loader from './components/Loader'
import CursorGrid from './components/CursorGrid'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import ProblemSection from './components/ProblemSection'
import FeatureExplainer from './components/FeatureExplainer'
import SpecsSection from './components/SpecsSection'
import SessionLogPreview from './components/SessionLogPreview'
import PhoneMockup from './components/PhoneMockup'
import './App.css'

function App() {
  const [loadingDone, setLoadingDone] = useState(false)
  const [phoneState, setPhoneState] = useState('idle')

  // Stable references so ProblemSection's ScrollTrigger effect doesn't
  // tear down and rebuild every time phoneState itself changes.
  const handlePhoneAnalyzing = useCallback(() => setPhoneState('analyzing'), [])
  const handlePhoneIdle = useCallback(() => setPhoneState('idle'), [])

  return (
    <>
      <CursorGrid />
      <Loader onComplete={() => setLoadingDone(true)} />
      <Navbar />

      <div className="stage">
        <div className="stage-copy">
          <Hero ready={loadingDone} />
          <ProblemSection
            onEnter={handlePhoneAnalyzing}
            onLeaveBack={handlePhoneIdle}
          />
        </div>
        <div className="stage-phone">
          <PhoneMockup state={phoneState} />
        </div>
      </div>

      <FeatureExplainer />
      <SpecsSection />
      <SessionLogPreview />

      {/* temporary — extra scroll height to test scroll-driven behavior; remove once the next section is built */}
      <div style={{ height: '80vh' }} aria-hidden="true" />
    </>
  )
}

export default App
