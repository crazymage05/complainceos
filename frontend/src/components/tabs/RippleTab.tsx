import type { RippleReport } from '../../services/api'
import QuickRippleForm from './QuickRippleForm'
import RippleAlertCard from '../RippleAlertCard'

interface Props {
  alerts: RippleReport[]
  onCheck: (description: string, effectiveDate: string) => void
  loading: boolean
}

export default function RippleTab({ alerts, onCheck, loading }: Props) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 space-y-3">
        <div>
          <h3 className="font-semibold text-inkSoft">Regulatory Ripple Detection</h3>
          <p className="text-xs text-inkMute mt-1">
            Paste or pick a regulation change. The agent traces which of your obligations it ripples into — directly and through dependency chains.
          </p>
        </div>
        <QuickRippleForm onCheck={onCheck} loading={loading} />
      </div>

      <div className="lg:col-span-2 space-y-3">
        <h3 className="font-semibold text-inkSoft">Ripple Alerts</h3>
        {alerts.length === 0 ? (
          <div className="os-card p-8 text-center text-inkFaint">
            <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <p className="text-sm font-medium text-inkMute">No ripple alerts yet</p>
            <p className="text-xs mt-1">Run a check on the left to see downstream impact across your obligations.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((r, i) => <RippleAlertCard key={i} {...r} />)}
          </div>
        )}
      </div>
    </div>
  )
}
