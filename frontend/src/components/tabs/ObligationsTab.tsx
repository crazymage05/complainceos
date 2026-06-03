import { useState } from 'react'
import clsx from 'clsx'
import type { ObligationInstance, DecayTrends } from '../../services/api'
import DecayScoreCard from '../DecayScoreCard'

interface Props {
  obligations: ObligationInstance[]
  loading: boolean
  onDraftClick: (id: string) => void
  onConfirm: (id: string) => void
  onDismiss: (id: string) => void
  trends?: DecayTrends
  onExplainClick?: (obligationName: string) => void
}

type Filter = 'all' | 'urgent' | 'warning' | 'proposed'

export default function ObligationsTab({
  obligations, loading, onDraftClick, onConfirm, onDismiss, trends, onExplainClick,
}: Props) {
  const [filter, setFilter] = useState<Filter>('all')

  const proposed = obligations.filter((o) => o.status === 'proposed')
  const active = obligations.filter((o) => o.status !== 'proposed')

  const counts = {
    all: active.length,
    urgent: active.filter((o) => o.decay_score < 20).length,
    warning: active.filter((o) => o.decay_score >= 20 && o.decay_score <= 40).length,
    proposed: proposed.length,
  }

  let shown: ObligationInstance[]
  if (filter === 'proposed') shown = proposed
  else if (filter === 'urgent') shown = active.filter((o) => o.decay_score < 20)
  else if (filter === 'warning') shown = active.filter((o) => o.decay_score >= 20 && o.decay_score <= 40)
  else shown = active
  shown = [...shown].sort((a, b) => a.decay_score - b.decay_score)

  const filters: { id: Filter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'urgent', label: 'Urgent' },
    { id: 'warning', label: 'Warning' },
    { id: 'proposed', label: 'Proposed' },
  ]

  if (loading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2, 3].map((i) => <div key={i} className="os-card p-5 h-24 animate-pulse" />)}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1.5 flex-wrap">
        {filters.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={clsx(
              'text-xs font-medium px-3 py-1.5 rounded-full border transition-colors flex items-center gap-1.5',
              filter === f.id
                ? 'bg-accent/15 text-accent-soft border-accent/40'
                : 'bg-white/5 text-inkMute border-edge hover:bg-white/10',
            )}
          >
            {f.label}
            <span className={clsx('text-[10px] px-1.5 rounded-full', filter === f.id ? 'bg-accent/20' : 'bg-white/10')}>
              {counts[f.id]}
            </span>
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <div className="os-card p-8 text-center text-inkFaint">
          <p className="text-sm font-medium text-inkMute">Nothing here</p>
          <p className="text-xs mt-1">No obligations match this filter.</p>
        </div>
      ) : filter === 'proposed' ? (
        <div className="space-y-3">
          {shown.map((o) => (
            <div key={o.instance_id} className="os-card border-l-4 border-l-indigo-500 p-5 flex items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300">AI-discovered</span>
                  <span className="text-xs text-inkFaint capitalize">{o.framework}</span>
                </div>
                <h3 className="font-semibold text-ink text-sm">{o.obligation_name}</h3>
                {o.description && <p className="text-xs text-inkMute mt-1">{o.description}</p>}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button onClick={() => onDismiss(o.instance_id)} className="os-btn-ghost text-xs px-3 py-1.5">Dismiss</button>
                <button onClick={() => onConfirm(o.instance_id)} className="os-btn-accent text-xs px-3 py-1.5">Add to plan</button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {shown.map((o) => (
            <DecayScoreCard
              key={o.instance_id}
              {...o}
              onDraftClick={onDraftClick}
              trend={trends?.[o.instance_id]}
              onExplainClick={onExplainClick}
            />
          ))}
        </div>
      )}
    </div>
  )
}
