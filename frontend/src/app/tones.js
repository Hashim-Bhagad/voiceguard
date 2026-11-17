import { AlertTriangle, CircleCheck, CircleHelp, ShieldAlert } from 'lucide-react'

// verdict().tone -> HeroUI colour + icon. Colour never carries meaning alone.
export const TONES = {
  high: { color: 'danger', text: 'text-danger', Icon: ShieldAlert },
  caution: { color: 'warning', text: 'text-warning', Icon: AlertTriangle },
  safe: { color: 'success', text: 'text-success', Icon: CircleCheck },
  neutral: { color: 'default', text: 'text-muted', Icon: CircleHelp },
}
