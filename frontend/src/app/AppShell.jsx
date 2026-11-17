import { Suspense, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { motion } from 'motion/react'
import { Button, Drawer } from '@heroui/react'
import { AudioLines, History as HistoryIcon, Menu, ShieldCheck, ArrowUpRight } from 'lucide-react'
import Logo from '@/components/Logo'
import { useAnalysis } from '@/lib/AnalysisContext'
import { verdict } from '@/lib/analysis'
import { BackendPill } from './components/ui'

const NAV = [
  { to: '/dashboard', label: 'Analyze', icon: AudioLines, end: true },
  { to: '/dashboard/challenge', label: 'Verify the caller', icon: ShieldCheck },
  { to: '/dashboard/log', label: 'History', icon: HistoryIcon, count: true },
]

function NavList({ onNavigate }) {
  const { history } = useAnalysis()
  const { pathname } = useLocation()
  const elevated = history.filter(r => verdict(r).tone === 'high' || r.challenge_triggered).length
  return (
    <nav aria-label="Workspace" className="flex flex-col gap-1">
      {NAV.map(item => {
        const active = item.end ? pathname === item.to : pathname.startsWith(item.to)
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={`relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors ${active ? 'text-foreground' : 'text-muted hover:text-foreground'}`}
          >
            {active && (
              <motion.span layoutId="rail-active" className="absolute inset-0 rounded-lg bg-default" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />
            )}
            <Icon aria-hidden className="relative size-4" strokeWidth={1.75} />
            <span className="relative">{item.label}</span>
            {item.count && elevated > 0 && (
              <span className="relative ml-auto rounded-md bg-danger/15 px-1.5 font-mono text-[0.68rem] text-danger tabular" aria-label={`${elevated} high-risk sessions`}>
                {elevated}
              </span>
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}

function RailFooter() {
  return (
    <div className="flex flex-col gap-4">
      <BackendPill />
      <a
        href="https://huggingface.co/Hashim-Bhagad/voiceguard-xlsr-aasist-indic"
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-foreground"
      >
        The model on Hugging Face <ArrowUpRight aria-hidden className="size-3.5" />
      </a>
    </div>
  )
}

const TITLES = { '/dashboard': 'Analyze', '/dashboard/challenge': 'Verify the caller', '/dashboard/log': 'History' }

export default function AppShell() {
  const { pathname } = useLocation()
  const title = TITLES[pathname] || 'Workspace'
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <div className="min-h-dvh bg-background lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      {/* Desktop rail */}
      <aside className="sticky top-0 hidden h-dvh flex-col justify-between border-r border-separator px-4 py-6 lg:flex">
        <div className="flex flex-col gap-10">
          <Logo className="px-2" />
          <NavList />
        </div>
        <div className="px-2"><RailFooter /></div>
      </aside>

      <div className="flex min-w-0 flex-col">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-separator bg-background/85 px-4 backdrop-blur lg:hidden">
          <Logo compact />
          <span className="truncate text-sm font-medium">{title}</span>
          <Button isIconOnly variant="ghost" size="sm" aria-label="Open navigation" onPress={() => setMenuOpen(true)}>
            <Menu className="size-5" />
          </Button>
          <Drawer.Backdrop isOpen={menuOpen} onOpenChange={setMenuOpen}>
            <Drawer.Content placement="left">
              <Drawer.Dialog className="flex h-full flex-col justify-between bg-background">
                <div className="flex flex-col gap-8">
                  <Drawer.Header>
                    <Drawer.Heading className="sr-only">Navigation</Drawer.Heading>
                    <Logo />
                  </Drawer.Header>
                  <Drawer.Body>
                    <NavList onNavigate={() => setMenuOpen(false)} />
                  </Drawer.Body>
                </div>
                <Drawer.Footer className="justify-start"><RailFooter /></Drawer.Footer>
              </Drawer.Dialog>
            </Drawer.Content>
          </Drawer.Backdrop>
        </header>

        <main id="main-content" tabIndex={-1} className="focus:outline-none mx-auto w-full max-w-[1180px] px-4 pb-24 pt-8 sm:px-8 lg:px-12 lg:pt-14">
          <Suspense fallback={<div className="min-h-[50vh]" role="status" aria-label="Loading" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
