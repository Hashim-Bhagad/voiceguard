import { Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { Menu, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import Logo from '../components/Logo'
import Cta from './Cta'
import { useBackend } from '../lib/backend'

const links = [
  ['#demo', 'Live demo'],
  ['#model', 'How it works'],
  ['#proof', 'Results'],
  ['#liveness', 'Liveness'],
]

function ModelStatus() {
  const { status } = useBackend()
  const map = {
    ready: ['bg-success', 'Model ready'],
    waking: ['bg-warning animate-pulse', 'Waking the model'],
    idle: ['bg-warning animate-pulse', 'Waking the model'],
    offline: ['bg-grey-700', 'Service offline · demos still work'],
  }
  const [dot, text] = map[status] || map.idle
  return (
    <span className="label-mono hidden items-center gap-2 normal-case tracking-normal lg:inline-flex" role="status">
      <span className={`size-1.5 rounded-full ${dot}`} aria-hidden="true" />
      {text}
    </span>
  )
}

export default function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  const toggle = useRef(null)
  // Escape closes the menu and puts focus back on the button that opened it.
  useEffect(() => {
    if (!open) return
    const onKey = e => { if (e.key === 'Escape') { setOpen(false); toggle.current?.focus() } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-4 pt-3 sm:px-6">
      <nav
        aria-label="Main"
        className={`mx-auto flex h-14 max-w-[1240px] items-center gap-6 rounded-2xl px-4 transition-[background-color,border-color,box-shadow] duration-500 ${scrolled ? 'glass' : 'border border-transparent'}`}
      >
        <Logo />
        <ul className="ml-4 hidden items-center gap-1 md:flex">
          {links.map(([href, label]) => (
            <li key={href}>
              <a href={href} className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:text-foreground">
                {label}
              </a>
            </li>
          ))}
        </ul>
        <div className="ml-auto flex items-center gap-4">
          <ModelStatus />
          <Cta to="/dashboard" variant="secondary" className="h-10! px-4! text-sm! max-sm:hidden">Open workspace</Cta>
          <button
            ref={toggle}
            type="button"
            className="grid size-10 place-items-center rounded-lg border border-border md:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'}
            onClick={() => setOpen(o => !o)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </nav>
      <AnimatePresence>
        {open && (
          <motion.div
            id="mobile-nav"
            className="glass mx-auto mt-2 max-w-[1240px] rounded-2xl p-2 md:hidden"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {links.map(([href, label]) => (
              <a key={href} href={href} onClick={() => setOpen(false)} className="block rounded-xl px-4 py-3 text-base">
                {label}
              </a>
            ))}
            <Link to="/dashboard" className="block rounded-xl px-4 py-3 text-base text-accent">Open workspace</Link>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
