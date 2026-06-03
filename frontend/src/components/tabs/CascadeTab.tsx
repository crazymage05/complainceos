import { useState } from 'react'
import clsx from 'clsx'
import { rippleCascade, type CascadeResponse } from '../../services/api'
import { pushToast } from '../Toaster'

const SEV_TONE: Record<string, string> = {
  high: 'bg-red-500/15 text-red-300',
  medium: 'bg-amber-500/15 text-amber-300',
  low: 'bg-accent/15 text-accent-soft',
}

const EXAMPLE = {
  title: 'GST rate revision for food services',
  description: 'GST rate revised for restaurant and cloud-kitchen services supplied through e-commerce operators under section 9(5)',
}

export default function CascadeTab() {
  const [title, setTitle] = useState(EXAMPLE.title)
  const [description, setDescription] = useState(EXAMPLE.description)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<CascadeResponse | null>(null)

  async function run() {
    if (!description.trim()) return
    setLoading(true)
    try {
      const res = await rippleCascade(title.trim() || 'Regulatory change', description.trim(), undefined, true)
      setResult(res)
    } catch {
      pushToast('Cascade failed — try again.', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="os-panel p-5">
        <h3 className="font-semibold text-ink">Multi-tenant Ripple Cascade</h3>
        <p className="text-xs text-inkMute mt-1 mb-4">
          One regulation change, evaluated across every business in the platform at once — showcasing MongoDB Atlas Vector + Atlas Search fused via RRF, running concurrently.
        </p>
        <div className="space-y-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Change title"
            className="os-input w-full px-3 py-2 text-sm"
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Describe the regulation change…"
            className="os-input w-full px-3 py-2 text-sm resize-none"
          />
          <button onClick={run} disabled={loading || !description.trim()} className="os-btn-accent px-4 py-2 text-sm flex items-center gap-2">
            {loading && <span className="w-4 h-4 border-2 border-canvas border-t-transparent rounded-full animate-spin" />}
            {loading ? 'Cascading across businesses…' : 'Run cascade'}
          </button>
        </div>
      </div>

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Evaluated" value={result.businesses_evaluated} />
            <Stat label="Affected" value={result.businesses_affected} accent />
            <Stat label="Elapsed" value={`${result.elapsed_ms} ms`} />
            <Stat label="Method" value={result.hybrid ? 'Hybrid RRF' : 'Vector'} />
          </div>

          <div className="os-panel overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-panel2 border-b border-edge">
                  <tr>
                    {['Business', 'State', 'Direct', 'Indirect', 'Severity'].map((h) => (
                      <th key={h} className="text-left text-[10px] font-bold uppercase tracking-wider text-inkMute px-4 py-2.5">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-edgeSoft">
                  {result.results.map((r) => (
                    <tr key={r.business_id} className="hover:bg-white/5 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-medium text-inkSoft truncate max-w-[200px]">{r.business_name}</p>
                        <p className="text-[10px] text-inkFaint capitalize">{r.industry}</p>
                      </td>
                      <td className="px-4 py-3 text-inkMute">{r.state}</td>
                      <td className="px-4 py-3 font-semibold text-ink">{r.direct_count}</td>
                      <td className="px-4 py-3 text-inkMute">{r.indirect_count}</td>
                      <td className="px-4 py-3">
                        <span className={clsx('text-[10px] font-bold uppercase px-2 py-0.5 rounded-full', SEV_TONE[r.severity] ?? SEV_TONE.low)}>
                          {r.severity}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="os-card p-4">
      <p className="text-[10px] font-bold uppercase tracking-wider text-inkFaint">{label}</p>
      <p className={clsx('text-2xl font-black mt-0.5', accent ? 'text-accent-soft' : 'text-ink')}>{value}</p>
    </div>
  )
}
