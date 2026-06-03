import { useState } from 'react'
import type { RippleReport } from '../services/api'

interface RippleAlertCardProps extends RippleReport {
  onViewDetails?: () => void
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function RippleAlertCard({
  change_title,
  effective_date,
  direct_impacts,
  indirect_impacts,
  total_affected,
  severity,
  onViewDetails,
}: RippleAlertCardProps) {
  const [expanded, setExpanded] = useState(false)

  const severityColors = {
    high: { card: 'border-red-500/40 bg-red-500/[0.07]', icon: 'text-red-400', badge: 'bg-red-500/15 text-red-300', dot: 'bg-red-500' },
    medium: { card: 'border-amber-500/40 bg-amber-500/[0.07]', icon: 'text-amber-400', badge: 'bg-amber-500/15 text-amber-300', dot: 'bg-amber-500' },
    low: { card: 'border-yellow-500/40 bg-yellow-500/[0.07]', icon: 'text-yellow-400', badge: 'bg-yellow-500/15 text-yellow-300', dot: 'bg-yellow-400' },
  }
  const sc = severityColors[severity] ?? severityColors.medium

  return (
    <div className={`rounded-xl border ${sc.card} p-5 shadow-panel`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={`flex-shrink-0 mt-0.5 ${sc.icon}`}>
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full uppercase tracking-wide ${sc.badge}`}>
              {severity} impact
            </span>
            <span className="text-xs text-inkMute">Effective {formatDate(effective_date)}</span>
          </div>
          <h3 className="font-semibold text-ink text-sm leading-snug">{change_title}</h3>
        </div>
      </div>

      {/* Counts */}
      <div className="mt-3 flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${sc.dot}`} />
          <span className="font-semibold text-inkSoft">{total_affected}</span>
          <span className="text-inkMute">obligations affected</span>
        </div>
        <div className="text-inkFaint text-xs">
          {direct_impacts.length} direct · {indirect_impacts.length} indirect
        </div>
      </div>

      {/* Expandable impacts */}
      {expanded && (
        <div className="mt-4 space-y-3">
          {direct_impacts.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-inkMute uppercase tracking-wide mb-1.5">Direct Impacts</p>
              <ul className="space-y-1">
                {direct_impacts.map((imp) => (
                  <li key={imp.obligation_id} className="flex items-start gap-2 text-xs text-inkSoft">
                    <svg className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                    </svg>
                    <span><span className="font-medium text-ink">{imp.obligation_name}</span> — {imp.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {indirect_impacts.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-inkMute uppercase tracking-wide mb-1.5">Indirect Impacts</p>
              <ul className="space-y-1">
                {indirect_impacts.map((imp) => (
                  <li key={imp.obligation_id} className="flex items-start gap-2 text-xs text-inkSoft">
                    <svg className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92z" />
                    </svg>
                    <span><span className="font-medium text-ink">{imp.obligation_name}</span> — {imp.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-xs font-medium text-inkMute hover:text-ink underline underline-offset-2 transition-colors"
        >
          {expanded ? 'Hide details' : 'Show affected obligations'}
        </button>
        {onViewDetails && (
          <button
            onClick={onViewDetails}
            className="ml-auto text-xs font-semibold px-3 py-1.5 bg-transparent border border-amber-500/30 text-amber-300 hover:bg-amber-500/10 rounded-lg transition-colors"
          >
            View Details
          </button>
        )}
      </div>
    </div>
  )
}
