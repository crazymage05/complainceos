import { useState } from 'react'
import clsx from 'clsx'

interface PenaltyBadgeProps {
  amount_inr: number
  days_late: number
  is_first_offense: boolean
}

function formatCurrency(amount: number): string {
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(1)}K`
  return `₹${amount.toLocaleString('en-IN')}`
}

export default function PenaltyBadge({
  amount_inr,
  days_late,
  is_first_offense,
}: PenaltyBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false)

  const { bg, text } =
    amount_inr > 5000
      ? { bg: 'bg-red-100', text: 'text-red-700' }
      : amount_inr >= 1000
      ? { bg: 'bg-amber-100', text: 'text-amber-700' }
      : { bg: 'bg-yellow-100', text: 'text-yellow-700' }

  return (
    <div className="relative inline-flex">
      <span
        className={clsx(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold cursor-help',
          bg,
          text
        )}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {formatCurrency(amount_inr)}
        <svg className="w-3 h-3 opacity-60" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
        </svg>
      </span>

      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-52 bg-gray-900 text-white rounded-lg p-3 text-xs shadow-xl pointer-events-none">
          <p className="font-semibold mb-1.5">Penalty Breakdown</p>
          <div className="space-y-1 text-gray-300">
            <div className="flex justify-between">
              <span>Days late</span>
              <span className="text-white font-medium">{days_late}d</span>
            </div>
            <div className="flex justify-between">
              <span>Estimated penalty</span>
              <span className="text-white font-medium">{formatCurrency(amount_inr)}</span>
            </div>
            {is_first_offense && (
              <div className="mt-1.5 pt-1.5 border-t border-gray-700 text-green-400 text-xs">
                First offense — reduced penalty may apply
              </div>
            )}
          </div>
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </div>
  )
}
