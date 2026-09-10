import { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, NavLink, Outlet, Link, useLocation } from 'react-router-dom'
import { MotionConfig, motion } from 'motion/react'
import { AnalysisProvider, useAnalysis } from './lib/AnalysisContext'
import { Brand, Icon } from './components/ui'
import './App.css'
import './pages/Dashboard.css'
const Landing = lazy(() => import('./pages/Landing'))
const LiveMonitoring = lazy(() => import('./pages/LiveMonitoring'))
const ChallengeResponse = lazy(() => import('./pages/ChallengeResponse'))
const AlertBanner = lazy(() => import('./pages/AlertBanner'))
const SessionLogPage = lazy(() => import('./pages/SessionLogPage'))
const links = [{ to: '/dashboard', label: 'Overview', icon: 'grid', end: true }, { to: '/dashboard/alert', label: 'Risk alerts', icon: 'alert' }, { to: '/dashboard/challenge', label: 'Liveness check', icon: 'shield' }, { to: '/dashboard/log', label: 'Session history', icon: 'history' }]
function DashboardLayout() {
  const { data, status, history } = useAnalysis()
  const location = useLocation()
  return <div className="workspace"><aside className="sidebar"><Brand /><span className="nav-label">WORKSPACE</span><nav aria-label="Workspace navigation">{links.map(item => {
    const active = item.end ? location.pathname === item.to : location.pathname.startsWith(item.to)
    return <NavLink key={item.to} to={item.to} end={item.end}>
      {active && <motion.span layoutId="rail-active" className="nav-active-pill" transition={{ type: 'spring', stiffness: 360, damping: 28 }} />}
      <Icon name={item.icon} />
      <span>{item.label}</span>
      {item.icon === 'alert' && data?.challenge_triggered && <span className="nav-count">1</span>}
    </NavLink>
  })}</nav><div className="sidebar-bottom"><div className="sidebar-note"><Icon name="lock" /><strong>Privacy starts here.</strong><p>Browser recordings are held in memory. Review service retention before uploading.</p></div><Link to="/#docs" className="sidebar-help"><Icon name="code" />Documentation<Icon name="external" size={15} /></Link><div className="workspace-identity"><span>TV</span><div>TRUST · VISHWAS<small>(Voice Impersonation Screening) · v1.0</small></div></div></div></aside><div className="workspace-main"><header className="workspace-topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{links.find(l => l.to === location.pathname)?.label || 'Overview'}</strong></div><div className="topbar-status"><span className={`status-dot ${status === 'analyzing' ? 'pulse' : ''}`} />{status === 'analyzing' ? 'Analyzing audio' : data?.source === 'demo' ? 'Demo session' : data?.source === 'live' ? 'API result received' : 'Ready to analyze'}<span className="avatar">TV</span></div></header><main id="main-content" className="workspace-content"><Suspense fallback={<div className="route-loading" role="status"><span className="spinner" />Opening workspace…</div>}><Outlet /></Suspense></main><footer className="workspace-footer"><span><Icon name="shield" size={14} /> Voice intelligence. Human confidence.</span><span>{history.length} session{history.length === 1 ? '' : 's'} this visit</span></footer></div></div>
}
function RouteEffects() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    document.title = pathname.startsWith('/dashboard') ? 'Workspace — TRUST & VISHWAS' : 'TRUST · VISHWAS — Voice Impersonation Screening'
    if (!hash) window.scrollTo({ top: 0, behavior: 'instant' })
    else { const timer = setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView(), 150); return () => clearTimeout(timer) }
  }, [pathname, hash])
  return null
}
export default function App() {
  return <MotionConfig reducedMotion="never" transition={{ duration: .22, ease: [.22, 1, .36, 1] }}><AnalysisProvider><a className="skip-link" href="#main-content">Skip to content</a><RouteEffects /><Suspense fallback={<div className="route-loading" role="status"><span className="spinner" />Opening TRUST & VISHWAS…</div>}><Routes><Route path="/" element={<Landing />} /><Route path="/dashboard" element={<DashboardLayout />}><Route index element={<LiveMonitoring />} /><Route path="alert" element={<AlertBanner />} /><Route path="challenge" element={<ChallengeResponse />} /><Route path="log" element={<SessionLogPage />} /></Route><Route path="*" element={<div className="not-found"><Brand /><h1>This page is off the grid.</h1><Link className="button primary" to="/dashboard">Open workspace <Icon name="arrow" /></Link></div>} /></Routes></Suspense></AnalysisProvider></MotionConfig>
}
