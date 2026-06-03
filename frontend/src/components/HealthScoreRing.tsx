import clsx from 'clsx'
import type { HealthScore } from '../services/api'

interface Props {
  data: HealthScore | null
  loading?: boolean
}

const BAND_TONE: Record<HealthScore['band'], { ring: string; text: string; bg: string; border: string; label: string }> = {
  excellent: { ring: '#10b981', text: 'text-accent-soft',  bg: 'bg-accent/[0.07]',  border: 'border-accent/30',  label: 'Excellent' },
  good:      { ring: '#22c55e', text: 'text-green-300',    bg: 'bg-green-500/[0.07]', border: 'border-green-500/30', label: 'Good' },
  fair:      { ring: '#f59e0b', text: 'text-amber-300',    bg: 'bg-amber-500/[0.07]', border: 'border-amber-500/30', label: 'Fair' },
  poor:      { ring: '#f97316', text: 'text-orange-300',   bg: 'bg-orange-500/[0.07]', border: 'border-orange-500/30', label: 'Poor' },
  critical:  { ring: '#ef4444', text: 'text-red-300',      bg: 'bg-red-500/[0.07]',   border: 'border-red-500/30',   label: 'Critical' },
}

function Ring({ score, color }: { score: number; color: string }) {
  const radius = 46
  const circ = 2 * Math.PI * radius
  const offset = circ - (Math.max(0, Math.min(100, score)) / 100) * circ
  return (
    <div className="relative w-32 h-32 flex-shrink-0">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={radius} fill="none" stroke="#27272A" strokeWidth="9" />
        <circle
          cx="55" cy="55" r={radius}
          fill="none" stroke={color} strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-black" style={{ color }}>{Math.round(score)}</span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-inkFaint">/ 100</span>
      </div>
    </div>
  )
}

export default function HealthScoreRing({ data, loading }: Props) {
  if (loading || !data) {
    return (
      <div className="os-panel p-5 flex items-center gap-5 animate-pulse">
        <div className="w-32 h-32 rounded-full bg-white/10" />
        <div className="flex-1 space-y-2">
          <div className="h-3 bg-white/10 rounded w-2/3" />
          <div className="h-2 bg-white/5 rounded w-1/2" />
          <div className="h-2 bg-white/5 rounded w-3/4" />
        </div>
      </div>
    )
  }

  const tone = BAND_TONE[data.band]
  const dims = [
    { label: 'Obligation freshness', d: data.dimensions.freshness },
    { label: 'On-time rate', d: data.dimensions.on_time_rate },
    { label: 'Recent ripple exposure', d: data.dimensions.ripple_exposure },
    { label: 'Overdue/red items', d: data.dimensions.overdue_penalty },
  ]

  return (
    <div className={clsx('rounded-2xl border shadow-panel p-5 flex items-center gap-6 flex-wrap', tone.bg, tone.border, tone.text)}>
      <Ring score={data.health_score} color={tone.ring} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-1">
          <p className="text-[10px] font-bold uppercase tracking-widest text-inkMute">Compliance Health</p>
          <span className={clsx('text-xs font-black px-2 py-0.5 rounded-md border border-current', tone.text)}>
            {tone.label.toUpperCase()}
          </span>
        </div>
        <h3 className="text-lg font-black text-ink leading-tight mb-3">
          {data.band === 'excellent' ? 'Your business is in great shape.'
            : data.band === 'good' ? 'You are on top of things.'
            : data.band === 'fair' ? 'A few items need attention.'
            : data.band === 'poor' ? 'Significant gaps to close.'
            : 'Multiple critical items overdue.'}
        </h3>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
          {dims.map(({ label, d }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="font-bold text-ink w-10">{Math.round(d.score)}</span>
              <span className="text-[10px] text-inkMute truncate">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
