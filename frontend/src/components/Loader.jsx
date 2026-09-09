import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import './Loader.css'

const BAR_COUNT = 28
const COUNT_DURATION_MS = 2400

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3)
}

function randomHeights() {
  return Array.from({ length: BAR_COUNT }, () => 10 + Math.random() * 90)
}

export default function Loader({ onComplete }) {
  const [percent, setPercent] = useState(0)
  const [visible, setVisible] = useState(true)
  const [levels, setLevels] = useState(randomHeights)
  const done = percent >= 100

  useEffect(() => {
    const start = performance.now()
    let frame

    function tick(now) {
      const t = Math.min(1, (now - start) / COUNT_DURATION_MS)
      setPercent(Math.round(easeOutCubic(t) * 100))
      if (t < 1) {
        frame = requestAnimationFrame(tick)
      }
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [])

  useEffect(() => {
    if (done) return
    const id = setInterval(() => setLevels(randomHeights()), 110)
    return () => clearInterval(id)
  }, [done])

  useEffect(() => {
    if (!done) return
    const id = setTimeout(() => setVisible(false), 350)
    return () => clearTimeout(id)
  }, [done])

  return (
    <AnimatePresence onExitComplete={onComplete}>
      {visible && (
        <motion.div
          className="loader"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, filter: 'blur(6px)' }}
          transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
        >
          <div className="loader-wordmark">VOICEGUARD</div>

          <div className="loader-meter" aria-hidden="true">
            {levels.map((h, i) => (
              <span
                key={i}
                className="loader-meter-bar"
                style={{ height: `${done ? 6 : h}%` }}
              />
            ))}
          </div>

          <div className="loader-readout">
            LOADING {String(percent).padStart(2, '0')}%
          </div>

          <div className="loader-track">
            <div
              className="loader-track-fill"
              style={{ width: `${percent}%` }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
