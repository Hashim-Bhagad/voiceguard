import { useEffect, useRef } from 'react'
import './CursorGrid.css'

export default function CursorGrid() {
  const ref = useRef(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    let frame = null
    let pending = null

    function apply() {
      frame = null
      if (!pending) return
      node.style.setProperty('--vg-mx', `${pending.x}px`)
      node.style.setProperty('--vg-my', `${pending.y}px`)
      pending = null
    }

    function handleMove(event) {
      pending = { x: event.clientX, y: event.clientY }
      if (frame === null) frame = requestAnimationFrame(apply)
    }

    function handleEnter() {
      node.style.setProperty('--vg-glow', '1')
    }

    function handleLeave() {
      node.style.setProperty('--vg-glow', '0')
    }

    window.addEventListener('mousemove', handleMove, { passive: true })
    document.documentElement.addEventListener('mouseenter', handleEnter)
    document.documentElement.addEventListener('mouseleave', handleLeave)

    return () => {
      window.removeEventListener('mousemove', handleMove)
      document.documentElement.removeEventListener('mouseenter', handleEnter)
      document.documentElement.removeEventListener('mouseleave', handleLeave)
      if (frame !== null) cancelAnimationFrame(frame)
    }
  }, [])

  return <div ref={ref} className="cursor-grid" aria-hidden="true" />
}
