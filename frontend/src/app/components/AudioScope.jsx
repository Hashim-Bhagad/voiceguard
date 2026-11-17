import { useEffect, useRef, useState } from 'react'
import { token } from '@/lib/tokens'

// Live microphone levels drawn as pixel columns, the same visual language as the
// landing hero. Reads the accent from the theme so it never hard-codes a colour.
export default function AudioScope({ stream, label = 'Live microphone input' }) {
  const canvas = useRef(null)
  const [failed, setFailed] = useState(false)
  const supported = typeof window !== 'undefined' && Boolean(window.AudioContext || window.webkitAudioContext)
  const unavailable = failed || !supported

  useEffect(() => {
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!stream || !canvas.current || !AudioCtx) return
    const context = new AudioCtx()
    const analyser = context.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.7
    const source = context.createMediaStreamSource(stream)
    source.connect(analyser)
    const values = new Uint8Array(analyser.frequencyBinCount)
    const node = canvas.current
    const brush = node.getContext('2d')
    const accent = token('--accent')
    const peaks = new Float32Array(40)
    let frame, last = 0, disposed = false

    function draw(now) {
      if (disposed) return
      frame = requestAnimationFrame(draw)
      if (document.hidden || now - last < 33) return
      last = now
      const w = node.clientWidth, h = node.clientHeight
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      if (node.width !== Math.round(w * ratio)) { node.width = Math.round(w * ratio); node.height = Math.round(h * ratio) }
      brush.setTransform(ratio, 0, 0, ratio, 0, 0)
      brush.clearRect(0, 0, w, h)
      analyser.getByteFrequencyData(values)
      const cols = peaks.length, gap = 3, cw = (w - gap * (cols - 1)) / cols
      const cell = 5, rows = Math.floor(h / (cell + 2))
      for (let i = 0; i < cols; i++) {
        const level = values[Math.floor((i / cols) * values.length * 0.8)] / 255
        const lit = Math.round(level * rows)
        peaks[i] = Math.max(lit, peaks[i] - 0.25)
        for (let r = 0; r < lit; r++) {
          brush.globalAlpha = 0.35 + 0.65 * (r / rows)
          brush.fillStyle = accent
          brush.fillRect(i * (cw + gap), h - (r + 1) * (cell + 2), cw, cell)
        }
        brush.globalAlpha = 0.5
        brush.fillRect(i * (cw + gap), h - (Math.round(peaks[i]) + 1) * (cell + 2), cw, cell)
      }
      brush.globalAlpha = 1
    }
    context.resume().then(() => { if (!disposed) frame = requestAnimationFrame(draw) }).catch(() => setFailed(true))
    return () => { disposed = true; cancelAnimationFrame(frame); source.disconnect(); analyser.disconnect(); void context.close() }
  }, [stream])

  return (
    <div className="relative h-24 w-full overflow-hidden rounded-lg bg-ink-0 px-3 pb-2 pt-6">
      <span className="label-mono absolute left-3 top-2">{unavailable ? 'Levels unavailable · recording continues' : label}</span>
      <canvas ref={canvas} className="size-full" aria-hidden="true" />
    </div>
  )
}
