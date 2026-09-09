import { useCallback, useState } from 'react'
import { Routes, Route, Link, NavLink, Outlet } from 'react-router-dom'
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
import { AnalysisProvider } from './lib/AnalysisContext'
import DocsSection from './components/DocsSection'
import Footer from './components/Footer'
import './App.css'
import './pages/Dashboard.css'

function DashNav() {
  return (
    <nav className="dash-nav" aria-label="Dashboard navigation">
      <NavLink to="/dashboard" end>Live Monitoring</NavLink>
      <NavLink to="/dashboard/alert">Alert</NavLink>
      <NavLink to="/dashboard/challenge">Challenge</NavLink>
      <NavLink to="/dashboard/log">Session Log</NavLink>
      <Link to="/">← Back to site</Link>
    </nav>
  )
}

// Layout route: wraps every /dashboard/* page in ONE AnalysisProvider so
// they all share the same live call state, and renders DashNav once
// instead of repeating it on every route like before.
function DashboardLayout() {
  return (
    <AnalysisProvider>
      <DashNav />
      <Outlet />
    </AnalysisProvider>
  )
}

function LandingPage() {
  const [loadingDone, setLoadingDone] = useState(false)
  const [phoneState, setPhoneState] = useState('idle')

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
      <DocsSection />
      <Footer />
    </>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />

      <Route path="/dashboard" element={<DashboardLayout />}>
        <Route index element={<LiveMonitoring />} />
        <Route path="alert" element={<AlertBanner />} />
        <Route path="challenge" element={<ChallengeResponse />} />
        <Route path="log" element={<SessionLogPage />} />
      </Route>
    </Routes>
  )
}

export default App
