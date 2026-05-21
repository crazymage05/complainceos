import clsx from 'clsx'
import { getScoreTailwind } from '../services/api'

interface DecayScoreCardProps {
  instance_id: string
  obligation_name: string
  deadline: string
  decay_score: number
  predicted_penalty_inr: number
  status: string
  onDraftClick: (instanceId: string) => void
}

function CircularScore({ score }: { score: number }) {
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const progress = Math.max(0, Math.min(100, score))
  const strokeDashoffset = circumference - (progress / 100) * circumference

  const color = score < 20 ? '#ef4444' : score <= 40 ? '#f59e0b' : '#22c55e'

  return (
    <div className="relative w-20 h-20 flex-shrink-0">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 72 72">
        <circle
          cx="36" cy="36" r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="7"
        />
        <circle
          cx="36" cy="36" r={radius}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span
          className="text-xl font-black"
          style={{ color }}
        >
          {score}
        </span>
      </div>
    </div>
  )
}

function formatCurrency(amount: number): string {
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(0)}K`
  return `₹${amount.toLocaleString('en-IN')}`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

function daysUntil(dateStr: string): number {
  const now = new Date()
  const d = new Date(dateStr)
  return Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}

export default function DecayScoreCard({
  instance_id,
  obligation_name,
  deadline,
  decay_score,
  predicted_penalty_inr,
  status,
  onDraftClick,
}: DecayScoreCardProps) {
  const colors = getScoreTailwind(decay_score)
  const days = daysUntil(deadline)

  const urgencyLabel =
    decay_score < 20 ? 'URGENT' : decay_score <= 40 ? 'WARNING' : 'ON TRACK'

  const statusColor =
    status === 'overdue'
      ? 'bg-red-100 text-red-700'
      : status === 'filed'
      ? 'bg-green-100 text-green-700'
      : status === 'in_progress'
      ? 'bg-blue-100 text-blue-700'
      : 'bg-gray-100 text-gray-600'

  return (
    <div
      className={clsx(
        'bg-white rounded-xl border-l-4 shadow-sm hover:shadow-md transition-shadow p-5 flex gap-4 items-start',
        colors.border
      )}
    >
      {/* Score Circle */}
      <CircularScore score={decay_score} />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3 className="font-semibold text-gray-900 text-sm leading-tight">{obligation_name}</h3>
          <span className={clsx('text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0', colors.badge)}>
            {urgencyLabel}
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            {formatDate(deadline)}
          </span>
          <span className={clsx(
            'font-medium',
            days < 0 ? 'text-red-600' : days <= 7 ? 'text-amber-600' : 'text-gray-500'
          )}>
            {days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? 'Due today!' : `${days}d left`}
          </span>
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {predicted_penalty_inr > 0 && (
              <span className="text-xs font-medium text-red-600 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                {formatCurrency(predicted_penalty_inr)} if missed
              </span>
            )}
            <span className={clsx('text-xs px-2 py-0.5 rounded-full', statusColor)}>
              {status.replace('_', ' ')}
            </span>
          </div>

          {decay_score < 40 && status !== 'filed' && (
            <button
              onClick={() => onDraftClick(instance_id)}
              className="text-xs font-semibold px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-lg transition-colors flex-shrink-0"
            >
              Prepare Draft
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
