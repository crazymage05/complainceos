import { useEffect, useState } from 'react'
import type { User } from 'firebase/auth'
import { getBusiness } from '../services/api'

interface Props {
  user: User
  businessId: string
  refreshSignal: number
  onEdit: () => void
  onSignOut: () => void
}

const TYPE_LABELS: Record<string, string> = {
  proprietorship: 'Sole Proprietorship',
  partnership: 'Partnership',
  pvt_ltd: 'Private Limited',
  llp: 'LLP',
  public_ltd: 'Public Limited',
}

function fmtINR(n?: number): string {
  if (!n && n !== 0) return '—'
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(2)} Cr`
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(2)} L`
  return `₹${n.toLocaleString('en-IN')}`
}

function fmtDate(s?: string): string {
  if (!s) return '—'
  const d = new Date(s)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-panel2 border border-edge rounded-xl px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-inkFaint">{label}</p>
      <p className="text-sm text-inkSoft mt-1 capitalize">{value || '—'}</p>
    </div>
  )
}

export default function ProfilePage({ user, businessId, refreshSignal, onEdit, onSignOut }: Props) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [biz, setBiz] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!businessId) { setLoading(false); return }
    setLoading(true)
    getBusiness(businessId)
      .then((b) => setBiz(b))
      .catch(() => setBiz(null))
      .finally(() => setLoading(false))
  }, [businessId, refreshSignal])

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="os-panel p-6 h-28 animate-pulse" />
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="os-card h-20 animate-pulse" />)}
        </div>
      </div>
    )
  }

  const registrations: string[] = biz?.registrations ?? []

  return (
    <div className="max-w-4xl space-y-6">
      {/* Identity header */}
      <div className="os-panel p-6 flex items-center gap-5 flex-wrap">
        {user.photoURL
          ? <img src={user.photoURL} alt="" className="w-16 h-16 rounded-2xl ring-1 ring-edge" />
          : <div className="w-16 h-16 rounded-2xl bg-accent/15 flex items-center justify-center text-2xl font-black text-accent-soft">
              {(biz?.name ?? 'B').charAt(0)}
            </div>}
        <div className="min-w-0 flex-1">
          <h2 className="text-2xl font-black text-ink truncate">{biz?.name ?? 'Your Business'}</h2>
          <p className="text-sm text-inkMute mt-0.5">
            {biz?.owner ? `${biz.owner} · ` : ''}{user.email}
          </p>
          {biz?.compliance_dna_version != null && (
            <span className="inline-block mt-2 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-accent/15 text-accent-soft">
              Compliance DNA v{biz.compliance_dna_version}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={onEdit} className="os-btn-accent text-sm px-4 py-2 flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Edit
          </button>
          <button onClick={onSignOut} className="os-btn-ghost text-sm px-4 py-2">Sign out</button>
        </div>
      </div>

      {/* Business details */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-widest text-inkMute mb-3">Business Details</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <Field label="Entity type" value={TYPE_LABELS[biz?.business_type] ?? biz?.business_type} />
          <Field label="Industry" value={biz?.industry?.replace(/_/g, ' ')} />
          <Field label="State" value={biz?.state} />
          <Field label="Employees" value={biz?.employee_count} />
          <Field label="Annual turnover" value={fmtINR(biz?.annual_turnover_inr)} />
          <Field label="Started" value={fmtDate(biz?.incorporation_date)} />
        </div>
      </div>

      {/* Registrations */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-widest text-inkMute mb-3">Registrations & Licenses</h3>
        {registrations.length === 0 ? (
          <div className="os-card p-5 text-sm text-inkFaint">No registrations on file. Use “Edit” to add GST, EPF, FSSAI, etc.</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {registrations.map((r) => (
              <span key={r} className="text-sm font-medium px-3 py-1.5 rounded-full bg-accent/10 text-accent-soft border border-accent/25">
                {r.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Account */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-widest text-inkMute mb-3">Account</h3>
        <div className="os-card divide-y divide-edgeSoft">
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-sm text-inkMute">Signed in as</span>
            <span className="text-sm text-inkSoft">{user.email}</span>
          </div>
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-sm text-inkMute">Business ID</span>
            <span className="text-xs text-inkFaint font-mono">{businessId}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
