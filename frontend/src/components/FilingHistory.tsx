import clsx from 'clsx'
import type { FilingHistory as FilingHistoryType } from '../services/api'
import PenaltyBadge from './PenaltyBadge'

interface FilingHistoryProps {
  history: FilingHistoryType[]
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatCurrency(amount: number): string {
  if (amount === 0) return '—'
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(1)}K`
  return `₹${amount.toLocaleString('en-IN')}`
}

export default function FilingHistory({ history }: FilingHistoryProps) {
  const onTime = history.filter((h) => h.status === 'on_time').length
  const late = history.filter((h) => h.status === 'late').length
  const pending = history.filter((h) => h.status === 'pending').length
  const total = history.length

  const onTimeRate = total > 0 ? Math.round((onTime / total) * 100) : 0
  const totalPenalties = history.reduce((sum, h) => sum + h.penalty_paid_inr, 0)
  const penaltiesAvoided = history
    .filter((h) => h.status === 'on_time')
    .reduce((sum) => sum + 1000, 0) // Example savings

  const rateColor =
    onTimeRate >= 80 ? 'text-green-600' : onTimeRate >= 60 ? 'text-amber-600' : 'text-red-600'

  const statusConfig = {
    on_time: { label: 'On Time', cls: 'bg-green-100 text-green-700' },
    late: { label: 'Late', cls: 'bg-red-100 text-red-700' },
    pending: { label: 'Pending', cls: 'bg-gray-100 text-gray-600' },
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* On-time rate — prominent */}
        <div className="col-span-2 sm:col-span-1 bg-white rounded-xl border border-gray-100 p-5 shadow-sm flex flex-col items-center justify-center text-center">
          <span className={clsx('text-5xl font-black', rateColor)}>{onTimeRate}%</span>
          <span className="text-xs text-gray-500 font-medium mt-1">On-Time Rate</span>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
          <p className="text-2xl font-bold text-gray-900">{onTime}</p>
          <p className="text-xs text-gray-500 mt-0.5">Filed on time</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
          <p className="text-2xl font-bold text-red-600">{late}</p>
          <p className="text-xs text-gray-500 mt-0.5">Filed late</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
          <p className="text-2xl font-bold text-amber-600">
            {totalPenalties > 0 ? formatCurrency(totalPenalties) : '₹0'}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">Total penalties</p>
        </div>
      </div>

      {/* Summary banner */}
      <div className="bg-green-50 border border-green-100 rounded-xl px-4 py-3 flex items-center gap-3">
        <svg className="w-5 h-5 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-gray-700">
          <span className="font-semibold text-green-700">{onTime} filings on time</span>,{' '}
          <span className="font-semibold text-red-600">{late} late</span>,{' '}
          <span className="font-semibold text-gray-500">{pending} pending</span>
          {penaltiesAvoided > 0 && (
            <> · <span className="font-semibold text-green-700">₹{penaltiesAvoided.toLocaleString('en-IN')} in penalties avoided</span></>
          )}
        </p>
      </div>

      {/* Table */}
      {history.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p className="text-sm font-medium">No filing history yet</p>
          <p className="text-xs mt-1">Your compliance records will appear here</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {['Obligation', 'Period', 'Filed Date', 'Deadline', 'Days Late', 'Penalty', 'Status'].map((h) => (
                    <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {history.map((row) => {
                  const sc = statusConfig[row.status]
                  return (
                    <tr key={row.filing_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3.5">
                        <span className="font-medium text-gray-900">{row.obligation_name}</span>
                      </td>
                      <td className="px-4 py-3.5 text-gray-600">{row.period}</td>
                      <td className="px-4 py-3.5 text-gray-600">{formatDate(row.filed_date)}</td>
                      <td className="px-4 py-3.5 text-gray-600">{formatDate(row.deadline)}</td>
                      <td className="px-4 py-3.5">
                        <span className={clsx(
                          'font-medium',
                          row.days_late === 0 ? 'text-green-600' :
                          row.days_late <= 7 ? 'text-amber-600' : 'text-red-600'
                        )}>
                          {row.days_late === 0 ? '—' : `${row.days_late}d`}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        {row.penalty_paid_inr > 0 ? (
                          <PenaltyBadge
                            amount_inr={row.penalty_paid_inr}
                            days_late={row.days_late}
                            is_first_offense={false}
                          />
                        ) : (
                          <span className="text-gray-400 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={clsx('text-xs font-semibold px-2.5 py-1 rounded-full', sc.cls)}>
                          {sc.label}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
