import { useRef } from 'react'
import { motion, useReducedMotion, useScroll, useTransform } from 'motion/react'

// Words that light up one by one as the reader scrolls through them: the wheel
// literally fills the sentence in. Reduced motion shows it fully lit.
function Word({ progress, range, children, accent }) {
  const opacity = useTransform(progress, range, [0.16, 1])
  return (
    <motion.span style={{ opacity }} className={accent ? 'text-accent' : undefined}>
      {children}{' '}
    </motion.span>
  )
}

export default function ScrubWords({ text, accentFrom = Infinity, className = '', as: Tag = 'p' }) {
  const ref = useRef(null)
  const reduce = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.85', 'end 0.4'] })
  const words = text.split(' ')
  if (reduce) return <Tag className={className}>{text}</Tag>
  return (
    <Tag ref={ref} className={className}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">
        {words.map((w, i) => (
          <Word key={i} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]} accent={i >= accentFrom}>
            {w}
          </Word>
        ))}
      </span>
    </Tag>
  )
}
