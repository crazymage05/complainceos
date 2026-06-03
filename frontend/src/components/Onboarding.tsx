import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createBusiness } from '../services/api'
import type { BusinessProfile } from '../services/api'
import clsx from 'clsx'

const STATES = [
  'Tamil Nadu', 'Maharashtra', 'Karnataka', 'Delhi', 'Gujarat', 'Other',
]

const INDUSTRIES = [
  { value: 'food_services', label: 'Food & Beverages' },
  { value: 'retail', label: 'Retail' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'services', label: 'Professional Services' },
  { value: 'construction', label: 'Construction' },
  { value: 'other', label: 'Other' },
]

const BUSINESS_TYPES = [
  { value: 'proprietorship', label: 'Sole Proprietorship' },
  { value: 'partnership', label: 'Partnership' },
  { value: 'pvt_ltd', label: 'Private Limited' },
  { value: 'llp', label: 'LLP' },
]

const REGISTRATIONS = [
  { id: 'GST', label: 'GST Registration' },
  { id: 'FSSAI', label: 'FSSAI License' },
  { id: 'EPF', label: 'EPF (Provident Fund)' },
  { id: 'ESI', label: 'ESI (Employee State Insurance)' },
  { id: 'Shop_License', label: 'Shop & Establishment License' },
  { id: 'Trade_License', label: 'Trade License' },
]

type FormData = Omit<BusinessProfile, 'registrations'> & {
  registrations: string[]
  incorporation_date: string
}

const DEFAULT_FORM: FormData = {
  business_name: '',
  owner_name: '',
  business_type: 'proprietorship',
  state: 'Tamil Nadu',
  industry: 'retail',
  employee_count: 0,
  annual_turnover_inr: 0,
  registrations: [],
  incorporation_date: '',
}

const LABEL = 'block text-sm font-semibold text-inkMute mb-1.5'
const FIELD = 'w-full os-input px-4 py-2.5 text-sm rounded-xl'

export default function Onboarding() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormData>(DEFAULT_FORM)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  function handleNumChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: parseFloat(value) || 0 }))
  }

  function toggleReg(id: string) {
    setForm((prev) => ({
      ...prev,
      registrations: prev.registrations.includes(id)
        ? prev.registrations.filter((r) => r !== id)
        : [...prev.registrations, id],
    }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await createBusiness(form)
      localStorage.setItem('business_id', result.business_id)
      localStorage.setItem('business_dna', JSON.stringify(result.dna))
      localStorage.setItem('business_name', form.business_name)
      navigate('/review')
    } catch {
      setError('Failed to create your compliance profile. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen bg-canvas flex items-center justify-center p-4 overflow-hidden">
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-accent/[0.08] blur-[130px]" />
      <div className="relative w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-accent rounded-2xl shadow-glow mb-3">
            <svg className="w-8 h-8 text-canvas" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-ink">ComplianceOS</h1>
          <p className="text-inkMute mt-1 text-sm">Build your compliance DNA in 2 minutes</p>
        </div>

        {/* Progress */}
        <div className="mb-6 flex items-center gap-3">
          <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
            <div className="h-full bg-accent rounded-full w-full transition-all duration-500" />
          </div>
          <span className="text-xs font-semibold text-accent-soft whitespace-nowrap">Step 1 of 1 — Business Profile</span>
        </div>

        {/* Form Card */}
        <form onSubmit={handleSubmit} className="os-panel shadow-panel p-8 space-y-6">

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-300 text-sm flex items-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              {error}
            </div>
          )}

          {/* Business & Owner Name */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={LABEL}>Business Name <span className="text-red-400">*</span></label>
              <input required name="business_name" value={form.business_name} onChange={handleChange}
                placeholder="e.g. Sharma Traders" className={FIELD} />
            </div>
            <div>
              <label className={LABEL}>Owner / Proprietor Name <span className="text-red-400">*</span></label>
              <input required name="owner_name" value={form.owner_name} onChange={handleChange}
                placeholder="e.g. Rajesh Sharma" className={FIELD} />
            </div>
          </div>

          {/* Business Type + State */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={LABEL}>Business Type <span className="text-red-400">*</span></label>
              <select name="business_type" value={form.business_type} onChange={handleChange}
                className={clsx(FIELD, '[color-scheme:dark]')}>
                {BUSINESS_TYPES.map((bt) => <option key={bt.value} value={bt.value}>{bt.label}</option>)}
              </select>
            </div>
            <div>
              <label className={LABEL}>State of Operation <span className="text-red-400">*</span></label>
              <select name="state" value={form.state} onChange={handleChange}
                className={clsx(FIELD, '[color-scheme:dark]')}>
                {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Industry */}
          <div>
            <label className={LABEL}>Industry / Sector <span className="text-red-400">*</span></label>
            <select name="industry" value={form.industry} onChange={handleChange}
              className={clsx(FIELD, '[color-scheme:dark]')}>
              {INDUSTRIES.map((i) => <option key={i.value} value={i.value}>{i.label}</option>)}
            </select>
          </div>

          {/* Incorporation Date */}
          <div>
            <label className={LABEL}>
              Business Start Date
              <span className="text-inkFaint font-normal ml-2">(optional — helps us tailor your obligations)</span>
            </label>
            <input type="date" name="incorporation_date" value={form.incorporation_date} onChange={handleChange}
              max={new Date().toISOString().split('T')[0]} className={clsx(FIELD, '[color-scheme:dark]')} />
            {form.incorporation_date && (() => {
              const months = Math.max(0, Math.floor(
                (Date.now() - new Date(form.incorporation_date).getTime()) / (1000 * 60 * 60 * 24 * 30)
              ))
              const label = months < 3 ? '🌱 Very new business — we\'ll start with essentials only'
                : months < 12 ? '📈 Growing business — moderate obligation set'
                : '🏢 Established business — full compliance profile'
              return <p className="text-xs mt-1.5 text-accent-soft font-medium">{label}</p>
            })()}
          </div>

          {/* Employees + Turnover */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={LABEL}>Number of Employees <span className="text-red-400">*</span></label>
              <input required type="number" name="employee_count" value={form.employee_count || ''}
                onChange={handleNumChange} placeholder="e.g. 12" min="0" className={FIELD} />
            </div>
            <div>
              <label className={LABEL}>Annual Turnover (₹) <span className="text-red-400">*</span></label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-inkMute text-sm font-medium">₹</span>
                <input required type="number" name="annual_turnover_inr" value={form.annual_turnover_inr || ''}
                  onChange={handleNumChange} placeholder="e.g. 5000000" min="0"
                  className={clsx(FIELD, 'pl-8')} />
              </div>
            </div>
          </div>

          {/* Registrations */}
          <div>
            <label className="block text-sm font-semibold text-inkMute mb-3">
              Existing Registrations & Licenses
              <span className="text-inkFaint font-normal ml-2">(select all that apply)</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {REGISTRATIONS.map((reg) => {
                const active = form.registrations.includes(reg.id)
                return (
                  <button
                    key={reg.id}
                    type="button"
                    onClick={() => toggleReg(reg.id)}
                    className={clsx(
                      'flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm font-medium transition-all text-left',
                      active
                        ? 'border-accent/40 bg-accent/10 text-accent-soft'
                        : 'border-edge bg-white/5 text-inkMute hover:bg-white/10'
                    )}
                  >
                    <div className={clsx(
                      'w-4 h-4 rounded flex-shrink-0 border-2 flex items-center justify-center',
                      active ? 'bg-accent border-accent' : 'border-edge'
                    )}>
                      {active && (
                        <svg className="w-2.5 h-2.5 text-canvas" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <span className="leading-tight">{reg.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="os-btn-accent w-full py-3.5 text-base flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-canvas border-t-transparent rounded-full animate-spin" />
                <span>Generating Compliance DNA…</span>
              </>
            ) : (
              <>
                <span>Generate My Compliance DNA</span>
                <span className="text-lg">→</span>
              </>
            )}
          </button>

          <p className="text-xs text-inkFaint text-center">
            We use this information to identify applicable regulations. Your data is encrypted and never shared.
          </p>
        </form>
      </div>
    </div>
  )
}
