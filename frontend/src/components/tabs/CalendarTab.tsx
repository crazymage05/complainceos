import { useMemo } from 'react'
import clsx from 'clsx'
import { getScoreColor, type ObligationInstance } from '../../services/api'

interface Props {
  obligations: ObligationInstance[]
  onDraftClick: (id: string) => void
}

const DOT: Record<'red' | 'amber' | 'green', string> = {
  red: 'bg-red-500',
  amber: 'bg-amber-500',
  green: 'bg-accent',
}

function monthKey(d: Date): string {
  return d.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
}

export default function CalendarTab({ obligations, onDraftClick }: Props) {
  const groups = useMemo(() => {
    const withDates = obligations
      .filter((o) => o.status !== 'proposed' && o.deadline)
      .map((o) => ({ o, date: new Date(o.deadline) }))
      .filter((x) => !isNaN(x.date.getTime()))
      .sort((a, b) => a.date.getTime() - b.date.getTime())

    const map = new Map<string, { o: ObligationInstance; date: Date }[]>()
    for (const item of withDates) {
      const key = monthKey(item.date)
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(item)
    }
    return Array.from(map.entries())
  }, [obligations])

  if (groups.length === 0) {
    return (
      <div className="os-card p-8 text-center text-inkFaint">
        <p className="text-sm font-medium text-inkMute">No scheduled deadlines</p>
        <p className="text-xs mt-1">Confirmed obligations with due dates will appear on this timeline.</p>
      </div>
    )
  }

  const now = Date.now()

  return (
    <div className="space-y-6">
      {groups.map(([month, items]) => (
        <div key={month}>
          <h3 className="text-xs font-bold uppercase tracking-widest text-inkMute mb-3">{month}</h3>
          <div className="os-panel divide-y divide-edgeSoft overflow-hidden">
            {items.map(({ o, date }) => {
              const color = getScoreColor(o.decay_score)
              const days = Math.ceil((date.getTime() - now) / 86400000)
              return (
                <div key={o.instance_id} className="flex items-center gap-4 px-4 py-3 hover:bg-white/5 transition-colors">
                  <div className="flex flex-col items-center justify-center w-12 flex-shrink-0">
                    <span className="text-lg font-black text-ink leading-none">{date.getDate()}</span>
                    <span className="text-[10px] text-inkFaint uppercase">{date.toLocaleDateString('en-IN', { month: 'short' })}</span>
                  </div>
                  <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', DOT[color])} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-inkSoft truncate">{o.obligation_name}</p>
                    <p className="text-xs text-inkFaint">
                      {days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? 'Due today' : `${days}d left`}
                      {o.predicted_penalty_inr > 0 && ` · up to ₹${o.predicted_penalty_inr.toLocaleString('en-IN')}`}
                    </p>
                  </div>
                  {o.decay_score < 40 && o.status !== 'filed' && (
                    <button onClick={() => onDraftClick(o.instance_id)} className="os-btn-ghost text-xs px-3 py-1.5 flex-shrink-0">
                      Prepare draft
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
