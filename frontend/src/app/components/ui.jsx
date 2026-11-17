import { Link } from 'react-router-dom'
import { buttonVariants, Chip } from '@heroui/react'
import { useBackend } from '@/lib/backend'

export function ButtonLink({ to, variant = 'secondary', size = 'md', className = '', children, ...props }) {
  return (
    <Link to={to} className={`${buttonVariants({ variant, size })} ${className}`} {...props}>
      {children}
    </Link>
  )
}

export function PageHeader({ title, children, action }) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="text-[clamp(1.75rem,3vw,2.375rem)] font-semibold leading-[1.1] tracking-[-0.025em] text-foreground">{title}</h1>
        {children && <p className="text-[0.975rem] leading-relaxed text-muted">{children}</p>}
      </div>
      {action}
    </header>
  )
}

export function SourceChip({ source }) {
  return source === 'demo'
    ? <Chip size="sm" variant="soft" color="default"><Chip.Label>Prepared demo</Chip.Label></Chip>
    : <Chip size="sm" variant="soft" color="accent"><Chip.Label>Live analysis</Chip.Label></Chip>
}

export function BackendPill({ className = '' }) {
  const { status } = useBackend()
  const view = {
    ready: { dot: 'bg-success', label: 'Model ready' },
    waking: { dot: 'bg-warning animate-pulse', label: 'Waking the model' },
    idle: { dot: 'bg-grey-700', label: 'Model asleep · wakes when you upload' },
    offline: { dot: 'bg-grey-700', label: 'Service offline · demos still work' },
  }[status]
  return (
    <span role="status" className={`inline-flex items-center gap-2 text-xs text-muted ${className}`}>
      <span aria-hidden className={`size-1.5 rounded-full ${view.dot}`} />
      {view.label}
    </span>
  )
}
