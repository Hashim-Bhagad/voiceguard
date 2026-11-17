import { useEffect, useRef, useState } from 'react'

/*
  Phone tilt as an input. Rolling the phone left or right steers x, tipping it
  toward or away steers y, both 0..1 around the angle the phone was held at when
  tilt was switched on (so any comfortable grip is "centre"). iOS asks for
  permission, which needs a tap, so tilt is always opt-in through `toggle`.

  state: 'off' | 'on' | 'unavailable' (no sensor events) | 'denied'
*/
export default function useTilt(onTilt) {
  const [state, setState] = useState('off')
  const cb = useRef(onTilt)
  useEffect(() => { cb.current = onTilt })

  useEffect(() => {
    if (state !== 'on') return
    let base = null, got = false
    let sx = 0.5, sy = 0.45
    const onOrient = e => {
      if (e.gamma == null || e.beta == null) return
      got = true
      // Keep "left/right" meaning left/right on screen in landscape too.
      const angle = screen.orientation?.angle ?? window.orientation ?? 0
      let lr = e.gamma, fb = e.beta
      if (angle === 90) { lr = e.beta; fb = -e.gamma }
      else if (angle === -90 || angle === 270) { lr = -e.beta; fb = e.gamma }
      if (!base) base = { lr, fb }
      // About 22 degrees of roll each way spans the meter; a small dead zone keeps a
      // resting hand from wobbling the bell.
      let dx = lr - base.lr
      if (Math.abs(dx) < 1.5) dx = 0
      const tx = 0.5 + dx / 44
      const ty = 0.45 + (fb - base.fb) / 70
      sx += (Math.min(1, Math.max(0, tx)) - sx) * 0.28
      sy += (Math.min(1, Math.max(0, ty)) - sy) * 0.28
      cb.current?.(sx, sy)
    }
    window.addEventListener('deviceorientation', onOrient)
    const probe = setTimeout(() => { if (!got) setState('unavailable') }, 1500)
    return () => { window.removeEventListener('deviceorientation', onOrient); clearTimeout(probe) }
  }, [state])

  const toggle = async () => {
    if (state === 'on') { setState('off'); return }
    const D = window.DeviceOrientationEvent
    if (!D) { setState('unavailable'); return }
    if (typeof D.requestPermission === 'function') {
      try {
        if ((await D.requestPermission()) !== 'granted') { setState('denied'); return }
      } catch { setState('denied'); return }
    }
    setState('on')
  }

  return [state, toggle]
}
