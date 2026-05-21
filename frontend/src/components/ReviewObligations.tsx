import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getObligations, confirmObligations, type ObligationInstance } from '../services/api'
import clsx from 'clsx'

const CATEGORY_ICONS: Record<string, string> = {
  GST: '🧾', EPF: '👷', ESI: '🏥', FSSAI: '🍽️',
  'Shops Act': '🏪', 'Companies Act': '🏢', 'Labour Laws': '⚖️',
  'Income Tax': '💰', 'Fire & Environment': '🔥', default: '📋',
}

function categoryIcon(cat: string) {
  for (const key of Object.keys(CATEGORY_ICONS)) {
    if (cat.includes(key)) return CATEGORY_ICONS[key]
  }
  return CATEGORY_ICONS.default
}

function groupByCategory(obs: ObligationInstance[]) {
  const map: Record<string, ObligationInstance[]> = {}
  for (const o of obs) {
    const cat = o.framework || 'Other'
    if (!map[cat]) map[cat] = []
    map[cat].push(o)
  }
  return map
}

export default function ReviewObligations() {
  const navigate = useNavigate()
  const businessId = localStorage.getItem('business_id') ?? ''
  const businessName = localStorage.getItem('business_name') ?? 'Your Business'

  const [obligations, setObligations] = useState<ObligationInstance[]>([])
  const [loading, setLoading] = useState(true)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [dueDates, setDueDates] = useState<Record<string, string>>({})
  const [confirming, setConfirming] = useState(false)
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!businessId) { navigate('/onboarding'); return }
    getObligations(businessId).then((obs) => {
      setObligations(obs)
      setChecked(new Set(obs.map((o) => o.instance_id)))
      const defaultDates: Record<string, string> = {}
      for (const o of obs) {
        if (o.deadline) {
          defaultDates[o.instance_id] = o.deadline.split('T')[0]
        }
      }
      setDueDates(defaultDates)
      // Expand all categories initially
      const cats = new Set(obs.map((_o) => _o.framework || 'Other'))
      setExpandedCats(cats)
      setLoading(false)
    }).catch(() => { setLoading(false) })
  }, [businessId, navigate])

  function toggleAll(_cat: string, obs: ObligationInstance[]) {
    const ids = obs.map((o) => o.instance_id)
    const allChecked = ids.every((id) => checked.has(id))
    setChecked((prev) => {
      const next = new Set(prev)
      ids.forEach((id) => allChecked ? next.delete(id) : next.add(id))
      return next
    })
  }

  function toggle(id: string) {
    setChecked((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function setDate(id: string, val: string) {
    setDueDates((prev) => ({ ...prev, [id]: val }))
  }

  async function handleConfirm() {
    setConfirming(true)
    try {
      const keepIds = Array.from(checked)
      const filteredDates: Record<string, string> = {}
      for (const id of keepIds) {
        if (dueDates[id]) filteredDates[id] = dueDates[id]
      }
      await confirmObligations(businessId, keepIds, filteredDates)
      navigate('/dashboard')
    } catch {
      setConfirming(false)
    }
  }

  const grouped = groupByCategory(obligations)
  const selectedCount = checked.size
  const totalCount = obligations.length

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-500 text-sm font-medium">Loading your compliance profile…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-emerald-50">
      <div className="max-w-3xl mx-auto px-4 py-8">

        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-green-500 rounded-2xl shadow-md mb-3">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Review Your Compliance DNA</h1>
          <p className="text-gray-500 mt-1 text-sm max-w-md mx-auto">
            AI identified <span className="font-semibold text-green-700">{totalCount} obligations</span> for <span className="font-semibold">{businessName}</span>.
            Uncheck anything that doesn't apply and set your own due dates.
          </p>
        </div>

        {/* Progress bar */}
        <div className="mb-6 bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center justify-between gap-4">
          <div className="flex-1">
            <div className="flex justify-between text-xs font-semibold text-gray-500 mb-1.5">
              <span>{selectedCount} selected</span>
              <span>{totalCount - selectedCount} removed</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 rounded-full transition-all duration-300"
                style={{ width: `${totalCount > 0 ? (selectedCount / totalCount) * 100 : 0}%` }}
              />
            </div>
          </div>
          <button
            onClick={handleConfirm}
            disabled={confirming || selectedCount === 0}
            className="flex-shrink-0 px-5 py-2.5 bg-green-500 hover:bg-green-600 disabled:bg-green-300 text-white font-semibold rounded-xl transition-all text-sm flex items-center gap-2"
          >
            {confirming ? (
              <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Saving…</>
            ) : (
              <>Confirm {selectedCount} Obligations →</>
            )}
          </button>
        </div>

        {/* Grouped obligations */}
        <div className="space-y-3">
          {Object.entries(grouped).map(([cat, obs]) => {
            const allChecked = obs.every((o) => checked.has(o.instance_id))
            const someChecked = obs.some((o) => checked.has(o.instance_id))
            const expanded = expandedCats.has(cat)

            return (
              <div key={cat} className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                {/* Category header */}
                <div
                  className="flex items-center justify-between px-5 py-3.5 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => setExpandedCats((prev) => {
                    const next = new Set(prev)
                    next.has(cat) ? next.delete(cat) : next.add(cat)
                    return next
                  })}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={allChecked}
                      ref={(el) => { if (el) el.indeterminate = someChecked && !allChecked }}
                      onChange={() => toggleAll(cat, obs)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-4 h-4 rounded accent-green-500 cursor-pointer"
                    />
                    <span className="text-lg">{categoryIcon(cat)}</span>
                    <span className="font-semibold text-gray-800 text-sm">{cat}</span>
                    <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full font-medium">
                      {obs.filter((o) => checked.has(o.instance_id)).length}/{obs.length}
                    </span>
                  </div>
                  <svg
                    className={clsx('w-4 h-4 text-gray-400 transition-transform', expanded && 'rotate-180')}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>

                {/* Obligation rows */}
                {expanded && (
                  <div className="border-t border-gray-50 divide-y divide-gray-50">
                    {obs.map((o) => {
                      const isChecked = checked.has(o.instance_id)
                      return (
                        <div
                          key={o.instance_id}
                          className={clsx(
                            'flex items-center gap-3 px-5 py-3 transition-colors',
                            isChecked ? 'bg-white' : 'bg-gray-50 opacity-60'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggle(o.instance_id)}
                            className="w-4 h-4 rounded accent-green-500 cursor-pointer flex-shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <p className={clsx(
                              'text-sm font-medium leading-tight',
                              isChecked ? 'text-gray-900' : 'text-gray-400 line-through'
                            )}>
                              {o.obligation_name}
                            </p>
                            <p className="text-xs text-gray-400 mt-0.5 capitalize">
                              {o.period} · {o.description || 'Statutory obligation'}
                            </p>
                          </div>
                          {isChecked && (
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              <span className="text-xs text-gray-400 hidden sm:block">Due:</span>
                              <input
                                type="date"
                                value={dueDates[o.instance_id] ?? ''}
                                onChange={(e) => setDate(o.instance_id, e.target.value)}
                                className="text-xs border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-green-400 w-32"
                              />
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Bottom confirm */}
        <div className="mt-6 flex justify-center">
          <button
            onClick={handleConfirm}
            disabled={confirming || selectedCount === 0}
            className="px-8 py-3.5 bg-green-500 hover:bg-green-600 disabled:bg-green-300 text-white font-semibold rounded-xl transition-all text-base flex items-center gap-2 shadow-sm"
          >
            {confirming ? (
              <><div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Saving your compliance profile…</>
            ) : (
              <>Confirm {selectedCount} obligations — Go to Dashboard →</>
            )}
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 mt-3">
          You can always add or remove obligations later from the dashboard.
        </p>
      </div>
    </div>
  )
}
