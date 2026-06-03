import clsx from 'clsx'
import type { BenchmarkResponse } from '../services/api'

interface Props {
  data: BenchmarkResponse | null
  loading?: boolean
}

const BAND_LABELS: Record<string, string> = {
  micro: 'Micro (<10 emp)',
  small: 'Small (10-49 emp)',
  medium: 'Medium (50-249 emp)',
  large: 'Large (250+ emp)',
}

function percentileTone(p: number | null): string {
  if (p === null) return 'text-inkFaint'
  if (p >= 80) return 'text-accent-soft'
  if (p >= 50) return 'text-amber-300'
  return 'text-red-300'
}

function percentileBg(p: number | null): string {
  if (p === null) return 'bg-white/5 border-edge'
  if (p >= 80) return 'bg-accent/[0.07] border-accent/30'
  if (p >= 50) return 'bg-amber-500/[0.07] border-amber-500/30'
  return 'bg-red-500/[0.07] border-red-500/30'
}

function percentileLabel(p: number | null): string {
  if (p === null) return '—'
  if (p >= 90) return 'Top 10%'
  if (p >= 75) return 'Top 25%'
  if (p >= 50) return 'Above average'
  if (p >= 25) return 'Below average'
  return 'Bottom 25%'
}

function PeerDimension({
  label, you, peer, percentile, formatter,
}: {
  label: string
  you: number | null | undefined
  peer: number | null | undefined
  percentile: number | null
  formatter: (n: number) => string
}) {
  const hasYou = you !== null && you !== undefined
  const youDisplay = hasYou ? formatter(you as number) : '—'
  const peerDisplay = peer === null || peer === undefined ? '—' : formatter(peer)
  return (
    <div className={clsx('rounded-xl border p-3 flex-1 min-w-0', percentileBg(percentile))}>
      <p className="text-[10px] font-bold uppercase tracking-widest text-inkMute">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <span className={clsx('text-2xl font-black', percentileTone(percentile))}>{youDisplay}</span>
        <span className="text-[10px] text-inkMute">you</span>
      </div>
      {hasYou ? (
        <div className="flex items-center justify-between mt-1 text-[11px]">
          <span className="text-inkMute">
            peers avg: <span className="font-bold text-ink">{peerDisplay}</span>
          </span>
          {percentile !== null && (
            <span className={clsx('font-bold', percentileTone(percentile))}>
              {percentileLabel(percentile)}
            </span>
          )}
        </div>
      ) : (
        <p className="mt-1 text-[11px] text-inkFaint">No filings yet — file once to compare with peers (avg {peerDisplay}).</p>
      )}
    </div>
  )
}

export default function BenchmarkCard({ data, loading }: Props) {
  if (loading || !data) {
    return (
      <div className="os-panel p-5 animate-pulse">
        <div className="h-3 bg-white/10 rounded w-1/3 mb-3" />
        <div className="grid grid-cols-2 gap-3">
          <div className="h-20 bg-white/5 rounded-xl" />
          <div className="h-20 bg-white/5 rounded-xl" />
        </div>
      </div>
    )
  }

  if (data.cohort.peer_count === 0) {
    return (
      <div className="os-panel p-5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-inkMute mb-1">Peer Benchmark</p>
        <p className="text-sm text-inkMute">
          No peer businesses found in <span className="font-bold capitalize">{data.cohort.industry}</span> {' '}
          ({BAND_LABELS[data.cohort.size_band] ?? data.cohort.size_band}). Add a few more businesses to enable comparisons.
        </p>
      </div>
    )
  }

  return (
    <div className="os-panel p-5">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-inkMute">
            Peer Benchmark
          </p>
          <p className="text-xs text-inkMute mt-0.5">
            Compared against <strong>{data.cohort.peer_count}</strong> similar businesses ({' '}
            <span className="capitalize">{data.cohort.industry}</span>, {BAND_LABELS[data.cohort.size_band] ?? data.cohort.size_band}
            {data.cohort.same_state_peer_count > 0 && ` · ${data.cohort.same_state_peer_count} in your state`}
            )
          </p>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap sm:flex-nowrap">
        <PeerDimension
          label="On-Time Filing Rate"
          you={data.on_time.your_rate}
          peer={data.on_time.cohort_avg_rate}
          percentile={data.on_time.percentile}
          formatter={(n) => `${Math.round(n * 100)}%`}
        />
        <PeerDimension
          label="Avg Decay Score"
          you={data.decay_health.your_avg_decay}
          peer={data.decay_health.cohort_avg_decay}
          percentile={data.decay_health.percentile}
          formatter={(n) => `${Math.round(n)}`}
        />
      </div>

      <p className="text-[10px] text-inkFaint mt-3 font-mono">
        Aggregation via $facet + $group across businesses + filing_history + obligation_instances
      </p>
    </div>
  )
}
