import { lazy, Suspense, useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { MotionConfig } from 'motion/react'
import { AnalysisProvider } from './lib/AnalysisContext'
import ClickBurst from './components/ClickBurst'
import PixelMorph from './components/PixelMorph'

const Landing = lazy(() => import('./pages/Landing'))
const AppShell = lazy(() => import('./app/AppShell'))
const Analyze = lazy(() => import('./app/Analyze'))
const Verify = lazy(() => import('./app/Verify'))
const History = lazy(() => import('./app/History'))
const NotFound = lazy(() => import('./pages/NotFound'))

function RouteEffects() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    document.title = pathname.startsWith('/dashboard')
      ? 'Workspace · VoiceGuard'
      : 'VoiceGuard · Voice clone detection'
    if (!hash) window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname, hash])
  return null
}

// Route loading: the logo grid cycling. It waits 250 ms before appearing, so a fast
// chunk load never flashes a loader.
function Loading() {
  return (
    <div className="grid min-h-dvh place-items-center bg-background" role="status" aria-label="Loading">
      <div className="flex animate-[loader-in_300ms_250ms_both] flex-col items-center gap-6">
        <PixelMorph size={72} loop />
        <span className="label-mono">Loading</span>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user" transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}>
      <AnalysisProvider>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-accent focus:px-4 focus:py-2 focus:text-accent-foreground">
          Skip to content
        </a>
        <RouteEffects />
        <ClickBurst />
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={<AppShell />}>
              <Route index element={<Analyze />} />
              <Route path="challenge" element={<Verify />} />
              <Route path="log" element={<History />} />
              <Route path="alert" element={<Navigate to="/dashboard/log" replace />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </AnalysisProvider>
    </MotionConfig>
  )
}
