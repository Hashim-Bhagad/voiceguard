import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'

// Landing calls to action are links (anchors or routes), so they're styled here
// rather than through HeroUI's <Button>, which renders a <button>.
const base =
  'group inline-flex items-center justify-center gap-2 rounded-[var(--radius)] px-5 h-12 text-[0.9375rem] font-medium transition-[transform,background-color,border-color,color] duration-200 ease-out active:scale-[0.98] focus-visible:outline-2'
const styles = {
  primary: `${base} bg-accent text-accent-foreground font-semibold hover:bg-[color-mix(in_oklab,var(--accent)_88%,white)]`,
  secondary: `${base} border border-border text-foreground hover:border-[color-mix(in_oklab,var(--accent)_45%,transparent)] hover:text-accent`,
  quiet: 'group inline-flex items-center gap-1.5 text-[0.9375rem] font-medium text-foreground underline decoration-[color-mix(in_oklab,var(--foreground)_30%,transparent)] underline-offset-[6px] transition-colors hover:text-accent hover:decoration-accent',
}

export default function Cta({ to, href, variant = 'primary', children, external = false, className = '', ...rest }) {
  const cls = `${styles[variant]} ${className}`
  const icon = external ? <ArrowUpRight className="size-4 transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" /> : null
  if (to) return <Link to={to} className={cls} {...rest}>{children}{icon}</Link>
  return (
    <a href={href} className={cls} {...(external ? { target: '_blank', rel: 'noreferrer' } : {})} {...rest}>
      {children}{icon}
    </a>
  )
}
