import type { ObligationInstance, RippleReport, DecayTrends } from '../../services/api'
import DecayScoreCard from '../DecayScoreCard'
import RippleAlertCard from '../RippleAlertCard'
import QuickRippleForm from './QuickRippleForm'

interface Props {
  obligations: ObligationInstance[]
  rippleAlerts: RippleReport[]
  loading: boolean
  onDraftClick: (id: string) => void
  onRippleCheck: (description: string, effectiveDate: string) => void
  rippleLoading: boolean
  trends?: DecayTrends
  onExplainClick?: (obligationName: string) => void
}

export default function OverviewTab({
  obligations, rippleAlerts, loading, onDraftClick, onRippleCheck, rippleLoading,
  trends, onExplainClick,
}: Props) {
  const urgent = obligations.filter((o) => o.decay_score < 20).slice(0, 3)
  const warning = obligations.filter((o) => o.decay_score >= 20 && o.decay_score <= 40).slice(0, 3)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <h3 className="font-semibold text-inkSoft">Urgent Attention Required</h3>
        {loading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="os-card p-5 animate-pulse h-24" />
            ))}
          </div>
        ) : urgent.length === 0 && warning.length === 0 ? (
          <div className="os-card p-8 text-center">
            <div className="w-12 h-12 bg-accent/10 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-accent-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="font-semibold text-inkSoft">All obligations on track</p>
            <p className="text-xs text-inkFaint mt-1">No urgent items at this time</p>
          </div>
        ) : (
          <div className="space-y-3">
            {[...urgent, ...warning].map((o) => (
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

      <div className="space-y-4">
        <h3 className="font-semibold text-inkSoft">Check Regulation Change</h3>
        <QuickRippleForm onCheck={onRippleCheck} loading={rippleLoading} compact />
        {rippleAlerts.length > 0 && (
          <>
            <h3 className="font-semibold text-inkSoft pt-2">Recent Ripple Alerts</h3>
            {rippleAlerts.slice(0, 2).map((r, i) => (
              <RippleAlertCard key={i} {...r} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
