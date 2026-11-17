import VoiceBars from './VoiceBars'
import { MaskLines, BlurIn } from './Reveal'
import Cta from './Cta'

// The close resolves: the meter returns, calm, and the single action waits.
export default function CloseSection() {
  return (
    <section className="relative isolate overflow-hidden px-6 pb-24 pt-[clamp(7rem,18vh,12rem)] sm:px-8" aria-labelledby="close-title">
      <div className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-[55%] opacity-50 [mask-image:linear-gradient(to_top,black_30%,transparent)]" aria-hidden="true">
        <VoiceBars calm density={0.8} ariaLabel="Calm voice meter" />
      </div>
      <div className="mx-auto flex max-w-[1240px] flex-col items-center text-center">
        <MaskLines as="h2" className="text-[clamp(3rem,8vw,7rem)] font-display font-normal leading-[0.92] tracking-[0.005em]">
          <span id="close-title">Hear the</span>
          <span className="text-accent">difference.</span>
        </MaskLines>
        <BlurIn delay={0.2} className="mt-10 flex flex-col items-center gap-8">
          <p className="max-w-md text-lg text-muted">Run a sample call in under ten seconds, or bring your own recording.</p>
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-4">
            <Cta href="#demo">Try a sample call</Cta>
            <Cta to="/dashboard" variant="quiet">Analyze your own audio</Cta>
          </div>
        </BlurIn>
      </div>
    </section>
  )
}
