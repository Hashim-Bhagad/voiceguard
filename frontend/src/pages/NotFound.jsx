import Logo from '../components/Logo'
import Cta from '../landing/Cta'

export default function NotFound() {
  return (
    <main id="main-content" tabIndex={-1} className="grain grid min-h-dvh place-items-center bg-background px-6 focus:outline-none">
      <div className="flex max-w-md flex-col items-start gap-6">
        <Logo />
        <p className="font-pixel text-7xl leading-none text-accent">404</p>
        <h1 className="font-display text-4xl leading-[1.05]">No signal on this line.</h1>
        <p className="text-muted">The page you dialled does not exist. The detector is still listening on the home page.</p>
        <Cta to="/">Back to the start</Cta>
      </div>
    </main>
  )
}
