import { forwardRef } from 'react'
import './PhoneMockup.css'

// A shared, stateless mockup reused across sections (App.jsx's Hero/Problem
// stage, and FeatureExplainer's pinned scroll section). `ref` exposes the
// rotating `.phone-mockup` element itself so a section can drive its tilt
// directly. `children`, when given, replaces the small idle/analyzing
// readout with custom on-screen content (used by FeatureExplainer for its
// per-state labels — a placeholder for the real per-state visuals later).
const PhoneMockup = forwardRef(function PhoneMockup(
  { state = 'idle', children },
  ref,
) {
  const analyzing = state === 'analyzing'

  return (
    <div className="phone-mockup-stage">
      <div
        ref={ref}
        className={`phone-mockup${analyzing ? ' phone-mockup--analyzing' : ''}`}
        aria-hidden="true"
      >
        <div className="phone-mockup-notch" />
        <div className="phone-mockup-screen">
          <div className="phone-mockup-glow" />
          {analyzing && <div className="phone-mockup-scan" />}
          {children ? (
            <div className="phone-mockup-content">{children}</div>
          ) : (
            <div className="phone-mockup-readout">
              <span className="phone-mockup-dot" />
              {analyzing ? 'ANALYZING' : 'STANDBY'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
})

export default PhoneMockup
