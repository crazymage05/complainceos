import { useEffect, useState } from 'react'
import clsx from 'clsx'
import {
  getDecisionsByAction, replayDecision,
  type AgentDecisionRow, type ActionCount, type ReplayResponse,
} from '../../services/api'
import { pushToast } from '../Toaster'

interface Props {
  businessId: string
}

function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

const ACTION_TONE: Record<string, string> = {
  ripple_detected: 'bg-amber-500/15 text-amber-300',
  penalty_predicted: 'bg-red-500/15 text-red-300',
  document_drafted: 'bg-blue-500/15 text-blue-300',
  decay_alert: 'bg-orange-500/15 text-orange-300',
  agent_run: 'bg-accent/15 text-accent-soft',
}

export default function DecisionsTab({ businessId }: Props) {
  const [decisions, setDecisions] = useState<AgentDecisionRow[]>([])
  const [counts, setCounts] = useState<ActionCount[]>([])
  const [activeAction, setActiveAction] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [replay, setReplay] = useState<Record<string, ReplayResponse>>({})
  const [replaying, setReplaying] = useState<string | null>(null)

  useEffect(() => {
    if (!businessId) return
    setLoading(true)
    getDecisionsByAction(businessId, activeAction ?? undefined)
      .then((res) => {
        setDecisions(res.decisions)
        if (!activeAction) setCounts(res.action_counts)
      })
      .catch(() => pushToast('Could not load the audit log.', 'error'))
      .finally(() => setLoading(false))
  }, [businessId, activeAction])

  async function handleReplay(id: string) {
    setReplaying(id)
    try {
      const res = await replayDecision(id)
      setReplay((prev) => ({ ...prev, [id]: res }))
    } catch {
      pushToast('Replay failed.', 'error')
    } finally {
      setReplaying(null)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-semibold text-inkSoft">Agent Decision Log</h3>
        <p className="text-xs text-inkMute mt-1">Every autonomous action the agent took, with full reasoning — replay any past decision against today's data.</p>
      </div>

      {/* Action filter chips */}
      {counts.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setActiveAction(null)}
            className={clsx('text-xs font-medium px-3 py-1.5 rounded-full border transition-colors',
              activeAction === null ? 'bg-accent/15 text-accent-soft border-accent/40' : 'bg-white/5 text-inkMute border-edge hover:bg-white/10')}
          >
            All
          </button>
          {counts.map((c) => (
            <button
              key={c.action}
              onClick={() => setActiveAction(c.action)}
              className={clsx('text-xs font-medium px-3 py-1.5 rounded-full border transition-colors flex items-center gap-1.5',
                activeAction === c.action ? 'bg-accent/15 text-accent-soft border-accent/40' : 'bg-white/5 text-inkMute border-edge hover:bg-white/10')}
            >
              {c.action.replace(/_/g, ' ')}
              <span className="text-[10px] px-1.5 rounded-full bg-white/10">{c.count}</span>
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => <div key={i} className="os-card p-4 h-16 animate-pulse" />)}
        </div>
      ) : decisions.length === 0 ? (
        <div className="os-card p-8 text-center text-inkFaint">
          <p className="text-sm font-medium text-inkMute">No decisions logged yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {decisions.map((d) => {
            const r = replay[d._id]
            return (
              <div key={d._id} className="os-card p-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={clsx('text-[10px] font-bold uppercase px-2 py-0.5 rounded-full', ACTION_TONE[d.action] ?? 'bg-white/5 text-inkMute')}>
                    {d.action.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs text-inkFaint">{fmtTime(d.timestamp)}</span>
                  {d.has_trace && (
                    <button
                      onClick={() => handleReplay(d._id)}
                      disabled={replaying === d._id}
                      className="ml-auto os-btn-ghost text-xs px-2.5 py-1 flex items-center gap-1.5"
                    >
                      {replaying === d._id
                        ? <span className="w-3 h-3 border-2 border-inkMute border-t-transparent rounded-full animate-spin" />
                        : <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>}
                      Replay
                    </button>
                  )}
                </div>
                {typeof d.payload?.details === 'string' && (
                  <p className="text-sm text-inkSoft mt-2">{d.payload.details as string}</p>
                )}
                {typeof d.payload?.final === 'string' && (d.payload.final as string).length > 0 && (
                  <p className="text-xs text-inkMute mt-1 line-clamp-2">{d.payload.final as string}</p>
                )}

                {r && (
                  <div className="mt-3 rounded-lg border border-edge bg-panel2 p-3">
                    {r.replayable ? (
                      <>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-accent-soft mb-1.5">
                          Re-ran against today's data · {r.diff?.length ?? 0} change{(r.diff?.length ?? 0) === 1 ? '' : 's'}
                        </p>
                        {(r.diff ?? []).slice(0, 6).map((dd, i) => (
                          <div key={i} className="text-xs text-inkMute flex gap-2">
                            <span className={clsx('font-bold',
                              dd.kind === 'added' ? 'text-accent-soft' : dd.kind === 'removed' ? 'text-red-400' : 'text-amber-400')}>
                              {dd.kind === 'added' ? '+' : dd.kind === 'removed' ? '−' : '~'}
                            </span>
                            <span className="font-mono">{dd.path}</span>
                          </div>
                        ))}
                        {(r.diff?.length ?? 0) === 0 && <p className="text-xs text-inkFaint">No differences — the decision still holds today.</p>}
                      </>
                    ) : (
                      <p className="text-xs text-inkFaint">{r.reason ?? 'This decision type cannot be replayed.'}</p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
