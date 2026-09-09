import { useCallback, useState } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import Loader from './components/Loader'
import CursorGrid from './components/CursorGrid'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import ProblemSection from './components/ProblemSection'
import FeatureExplainer from './components/FeatureExplainer'
import SpecsSection from './components/SpecsSection'
import SessionLogPreview from './components/SessionLogPreview'
import PhoneMockup from './components/PhoneMockup'
import LiveMonitoring from './pages/LiveMonitoring'
import AlertBanner from './pages/AlertBanner'
import ChallengeResponse from './pages/ChallengeResponse'
import SessionLogPage from './pages/SessionLogPage'
import './App.css'
import './pages/Dashboard.css'

function DashNav() {
  return (
    <nav className="dash-nav">
      <Link to="/dashboard">Live Monitoring</Link>
      <Link to="/dashboard/alert">Alert</Link>
      <Link to="/dashboard/challenge">Challenge</Link>
      <Link to="/dashboard/log">Session Log</Link>
      <Link to="/">← Back to site</Link>
    </nav>
  )
}

function LandingPage() {
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

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/dashboard"
        element={
          <>
            <DashNav />
            <LiveMonitoring />
          </>
        }
      />
      <Route
        path="/dashboard/alert"
        element={
          <>
            <DashNav />
            <AlertBanner />
          </>
        }
      />
      <Route
        path="/dashboard/challenge"
        element={
          <>
            <DashNav />
            <ChallengeResponse />
          </>
        }
      />
      <Route
        path="/dashboard/log"
        element={
          <>
            <DashNav />
            <SessionLogPage />
          </>
        }
      />
    </Routes>
  )
}

export default App