import type { ExposureForecast } from '../services/api'

interface Props {
  data: ExposureForecast | null
  loading?: boolean
}

function formatINR(n: number): string {
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(2)}Cr`
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(2)}L`
  if (n >= 1000) return `₹${(n / 1000).toFixed(1)}k`
  return `₹${Math.round(n).toLocaleString('en-IN')}`
}

const HORIZON_LABELS: Record<number, string> = {
  30: '30 days',
  60: '60 days',
  90: '90 days',
}

export default function ExposureForecastCard({ data, loading }: Props) {
  if (loading || !data) {
    return (
      <div className="os-panel p-5 animate-pulse">
        <div className="h-3 bg-white/10 rounded w-1/3 mb-3" />
        <div className="grid grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 bg-white/5 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (data.total_pending === 0) return null

  const maxExposure = Math.max(
    data.current_exposure_inr,
    ...data.by_horizon.map((h) => h.exposure_inr),
    1,
  )

  return (
    <div className="os-panel p-5">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-inkMute">
            Penalty Exposure Forecast
          </p>
          <p className="text-xs text-inkMute mt-0.5">
            If you do nothing — projection across MongoDB Time Series snapshots
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold uppercase tracking-widest text-inkMute">Today</p>
          <p className="text-xl font-black text-ink">{formatINR(data.current_exposure_inr)}</p>
        </div>
      </div>

      {/* Horizons row */}
      <div className="grid grid-cols-3 gap-3">
        {data.by_horizon.map((h) => {
          const pct = Math.min(100, (h.exposure_inr / maxExposure) * 100)
          const tone = h.delta_inr >= h.exposure_inr * 0.5
            ? 'text-red-400'
            : h.delta_inr > 0
              ? 'text-amber-400'
              : 'text-accent-soft'
          return (
            <div key={h.days} className="bg-panel2 rounded-xl border border-edge p-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-inkMute">
                +{HORIZON_LABELS[h.days] ?? `${h.days}d`}
              </p>
              <p className="text-2xl font-black text-ink mt-0.5">
                {formatINR(h.exposure_inr)}
              </p>
              <p className={`text-xs mt-0.5 ${tone}`}>
                {h.delta_inr >= 0 ? '+' : ''}{formatINR(h.delta_inr)} vs today
              </p>
              {/* Mini bar */}
              <div className="mt-2 h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-orange-400 to-red-500 rounded-full transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
              {h.newly_red_count > 0 && (
                <p className="text-[10px] text-red-400 font-semibold mt-1.5">
                  +{h.newly_red_count} newly overdue
                </p>
              )}
            </div>
          )
        })}
      </div>

      {/* Top contributors */}
      {data.top_contributors.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-widest text-inkMute hover:text-inkSoft">
            What drives the {HORIZON_LABELS[Math.max(...data.horizons_days)] ?? '90 day'} exposure ({data.top_contributors.length} top items)
          </summary>
          <div className="mt-2 space-y-1.5">
            {data.top_contributors.map((c, i) => (
              <div key={i} className="flex items-center justify-between text-xs gap-2 py-1.5 border-b border-edgeSoft last:border-0">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink truncate">{c.name}</p>
                  <p className="text-[10px] text-inkMute">
                    {c.days_late_at_horizon} days late at horizon
                  </p>
                </div>
                <p className="text-sm font-black text-red-300 flex-shrink-0">
                  {formatINR(c.amount_inr)}
                </p>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
