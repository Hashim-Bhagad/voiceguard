import { Children, isValidElement } from 'react'
import { motion, useReducedMotion } from 'motion/react'

const EASE = [0.16, 1, 0.3, 1]
const view = { once: true, amount: 0.35 }

/*
  Line-by-line masked reveal: each child is one line that slides up from behind its
  own overflow mask. Pass lines as children, e.g.
    <MaskLines as="h2"><span>One voice.</span><span>Two intentions.</span></MaskLines>
  The text is real markup and visible to crawlers and screen readers throughout;
  only transform and opacity animate.
*/
export function MaskLines({ as = 'div', children, className = '', delay = 0, stagger = 0.08, lineClassName = '' }) {
  const reduce = useReducedMotion()
  const Tag = motion[as] || motion.div
  const lines = Children.toArray(children).filter(isValidElement)
  return (
    <Tag className={className} initial="hidden" whileInView="shown" viewport={view}>
      {lines.map((line, i) => (
        <span key={i} className={`block overflow-hidden pb-[0.08em] ${lineClassName}`}>
          <motion.span
            className="block will-change-transform"
            variants={{
              hidden: reduce ? { opacity: 0 } : { y: '105%' },
              shown: reduce ? { opacity: 1 } : { y: '0%' },
            }}
            transition={{ duration: reduce ? 0.3 : 0.9, ease: EASE, delay: delay + i * stagger }}
          >
            {line}
          </motion.span>
        </span>
      ))}
    </Tag>
  )
}

// Blur-to-sharp for short text and small elements (blur is costly on big areas).
export function BlurIn({ as = 'div', children, className = '', delay = 0, y = 14 }) {
  const reduce = useReducedMotion()
  const Tag = motion[as] || motion.div
  return (
    <Tag
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y, filter: 'blur(8px)' }}
      whileInView={reduce ? { opacity: 1 } : { opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={view}
      transition={{ duration: reduce ? 0.3 : 0.8, ease: EASE, delay }}
    >
      {children}
    </Tag>
  )
}

// Cards and panels: a small scale-in, staggered by the caller through `delay`.
export function ScaleIn({ as = 'div', children, className = '', delay = 0 }) {
  const reduce = useReducedMotion()
  const Tag = motion[as] || motion.div
  return (
    <Tag
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 24 }}
      whileInView={reduce ? { opacity: 1 } : { opacity: 1, scale: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: reduce ? 0.3 : 0.9, ease: EASE, delay }}
    >
      {children}
    </Tag>
  )
}
