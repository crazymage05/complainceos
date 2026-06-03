import { useEffect, useState } from 'react'
import clsx from 'clsx'
import { getBusiness, updateBusiness } from '../services/api'
import { pushToast } from './Toaster'

interface Props {
  businessId: string
  open: boolean
  onClose: () => void
  onSaved: () => void
}

const ALL_REGISTRATIONS = ['GST', 'EPF', 'ESI', 'FSSAI', 'Shop_License', 'Trade_License', 'PT']
const STATES = [
  'Tamil Nadu', 'Maharashtra', 'Karnataka', 'Delhi', 'Gujarat', 'Telangana',
  'West Bengal', 'Uttar Pradesh', 'Kerala', 'Rajasthan',
]

export default function EditProfileModal({ businessId, open, onClose, onSaved }: Props) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [employeeCount, setEmployeeCount] = useState(0)
  const [turnover, setTurnover] = useState(0)
  const [state, setState] = useState('')
  const [registrations, setRegistrations] = useState<string[]>([])

  useEffect(() => {
    if (!open || !businessId) return
    setLoading(true)
    getBusiness(businessId)
      .then((b) => {
        setEmployeeCount(b.employee_count ?? 0)
        setTurnover(b.annual_turnover_inr ?? 0)
        setState(b.state ?? '')
        setRegistrations(b.registrations ?? [])
      })
      .catch(() => pushToast('Could not load profile.', 'error'))
      .finally(() => setLoading(false))
  }, [open, businessId])

  if (!open) return null

  function toggleReg(r: string) {
    setRegistrations((prev) => prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r])
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateBusiness(businessId, {
        employee_count: Number(employeeCount),
        annual_turnover_inr: Number(turnover),
        state,
        registrations,
      })
      pushToast('Profile updated — recomputing your compliance DNA.', 'success')
      onSaved()
      onClose()
    } catch {
      pushToast('Save failed — try again.', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative os-panel shadow-glow w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-edge sticky top-0 bg-panel">
          <h2 className="font-bold text-ink">Edit business profile</h2>
          <button onClick={onClose} className="text-inkFaint hover:text-ink transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {loading ? (
          <div className="p-10 flex justify-center">
            <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="p-6 space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-inkMute mb-1.5">Employees</label>
                <input type="number" min={0} value={employeeCount}
                  onChange={(e) => setEmployeeCount(Number(e.target.value))}
                  className="os-input w-full px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-inkMute mb-1.5">Annual turnover (₹)</label>
                <input type="number" min={0} value={turnover}
                  onChange={(e) => setTurnover(Number(e.target.value))}
                  className="os-input w-full px-3 py-2 text-sm" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-inkMute mb-1.5">State</label>
              <select value={state} onChange={(e) => setState(e.target.value)}
                className="os-input w-full px-3 py-2 text-sm [color-scheme:dark]">
                {!STATES.includes(state) && state && <option value={state}>{state}</option>}
                {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-inkMute mb-2">Registrations</label>
              <div className="flex flex-wrap gap-2">
                {ALL_REGISTRATIONS.map((r) => {
                  const active = registrations.includes(r)
                  return (
                    <button key={r} onClick={() => toggleReg(r)}
                      className={clsx(
                        'text-xs font-medium px-3 py-1.5 rounded-full border transition-colors',
                        active
                          ? 'bg-accent/15 text-accent-soft border-accent/40'
                          : 'bg-white/5 text-inkMute border-edge hover:bg-white/10',
                      )}>
                      {r.replace(/_/g, ' ')}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        <div className="px-6 py-4 border-t border-edge flex justify-end gap-2 sticky bottom-0 bg-panel">
          <button onClick={onClose} className="os-btn-ghost px-4 py-2 text-sm">Cancel</button>
          <button onClick={handleSave} disabled={saving || loading} className="os-btn-accent px-4 py-2 text-sm flex items-center gap-2">
            {saving && <span className="w-4 h-4 border-2 border-canvas border-t-transparent rounded-full animate-spin" />}
            Save changes
          </button>
        </div>
      </div>
    </div>
  )
}
