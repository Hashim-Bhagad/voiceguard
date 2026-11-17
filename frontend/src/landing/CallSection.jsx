import { MaskLines, BlurIn } from './Reveal'
import PhoneCall from './PhoneCall'
import ScrubWords from './ScrubWords'

// The quiet before the peak: the scam plays out on a phone as the reader scrolls,
// then one sentence fills in under the wheel.
export default function CallSection() {
  return (
    <section className="relative px-6 py-[clamp(7rem,18vh,12rem)] sm:px-8" aria-labelledby="call-title">
      <div className="mx-auto grid max-w-[1240px] items-center gap-20 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <PhoneCall />
        <div className="flex flex-col items-start gap-12 lg:items-end lg:text-right">
          <h2 id="call-title" className="sr-only">A familiar voice asking for money</h2>
          <MaskLines
            as="blockquote"
            className="font-mono text-[clamp(1.15rem,2.2vw,1.75rem)] leading-[1.4] text-foreground"
            stagger={0.45}
          >
            <span>“Beta, it’s me. Don’t panic.”</span>
            <span>“I need fifty thousand, right now.”</span>
            <span className="text-accent">“And don’t tell your mother.”</span>
          </MaskLines>
          <BlurIn delay={0.3} className="max-w-md">
            <p className="text-xl font-medium tracking-[-0.01em] text-foreground">It sounds exactly like them. That is the point.</p>
            <p className="mt-4 leading-relaxed text-muted">
              A few seconds of someone’s voice and a free tool are enough to clone it. The calls come in
              Hindi, Hinglish, Tamil, in whatever language the listener trusts.
            </p>
          </BlurIn>
        </div>
      </div>
      <div className="mx-auto mt-[clamp(6rem,14vh,9rem)] max-w-[1240px]">
        <ScrubWords
          text="The voice itself is no longer evidence."
          accentFrom={4}
          className="max-w-[18ch] font-display text-[clamp(2.5rem,6.4vw,5.75rem)] leading-[1] tracking-[0.005em]"
        />
      </div>
    </section>
  )
}
