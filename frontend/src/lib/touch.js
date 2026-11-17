// Touch-first helpers. Phones get their own effects in place of the cursor ones:
// the thumb, the tilt of the phone and the scroll are the inputs there.

// A phone or tablet: no hover, a finger as the primary pointer.
export const isTouch = () =>
  typeof window !== 'undefined' && window.matchMedia('(hover: none) and (pointer: coarse)').matches

export const prefersReduced = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// A short haptic tick where the platform allows it (Android Chrome; iOS Safari has no
// Vibration API and ignores this). Browsers only buzz after the visitor has touched
// the page, so automatic animations never vibrate on their own.
export function haptic(pattern = 8) {
  try {
    if (prefersReduced()) return
    if (navigator.userActivation && !navigator.userActivation.hasBeenActive) return
    navigator.vibrate?.(pattern)
  } catch { /* unsupported */ }
}

// Interactive elements own their own press feedback (ClickBurst).
export const INTERACTIVE = 'a[href], button, input, select, textarea, label, summary, [role="button"], [role="tab"], [role="option"], [role="slider"], [data-touch-surface]'
