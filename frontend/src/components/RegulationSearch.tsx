import { useState, useEffect, useRef } from 'react'
import clsx from 'clsx'
import { searchRegulations, type RegulationSearchResult } from '../services/api'

const CATEGORY_LABELS: Record<string, string> = {
  taxation: 'Taxation',
  labour: 'Labour',
  food_safety: 'Food Safety',
  shops_establishments: 'Shops Act',
  companies_act: 'Companies Act',
  corporate: 'Companies Act',
  fire_safety: 'Fire Safety',
  environmental: 'Environmental',
  income_tax: 'Income Tax',
}

const CATEGORY_TONES: Record<string, string> = {
  taxation: 'bg-blue-500/15 text-blue-300',
  labour: 'bg-purple-500/15 text-purple-300',
  food_safety: 'bg-orange-500/15 text-orange-300',
  shops_establishments: 'bg-cyan-500/15 text-cyan-300',
  companies_act: 'bg-indigo-500/15 text-indigo-300',
  corporate: 'bg-indigo-500/15 text-indigo-300',
  fire_safety: 'bg-red-500/15 text-red-300',
  environmental: 'bg-accent/15 text-accent-soft',
  income_tax: 'bg-yellow-500/15 text-yellow-300',
}

function formatINR(n?: number): string {
  if (n === undefined || n === null) return '—'
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(1)}Cr`
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(1)}L`
  return `₹${n.toLocaleString('en-IN')}`
}

/**
 * Regulation finder — uses MongoDB Atlas Search ($search) for relevance-
 * scored full-text queries over the 90-regulation corpus. Debounced as you
 * type; falls back to $regex if the Atlas Search index isn't configured.
 */
export default function RegulationSearch() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<RegulationSearchResult[]>([])
  const [method, setMethod] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Debounced search
  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([])
      setMethod('')
      return
    }
    setLoading(true)
    setError(null)
    const handle = setTimeout(async () => {
      try {
        const res = await searchRegulations(q.trim())
        setResults(res.results)
        setMethod(res.method)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Search failed')
      } finally {
        setLoading(false)
      }
    }, 250)
    return () => clearTimeout(handle)
  }, [q])

  // Click outside to close
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-inkFaint" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 110-16 8 8 0 010 16z" />
        </svg>
        <input
          type="text"
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          placeholder="Search 90 Indian regulations… (e.g. GSTR-9, FSSAI, EPF)"
          className="w-full os-input pl-9 pr-3 py-2 text-sm rounded-xl"
        />
        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        )}
      </div>

      {open && q.length >= 2 && (results.length > 0 || error || (!loading && results.length === 0)) && (
        <div className="absolute z-30 mt-1.5 w-full max-h-96 overflow-y-auto os-panel shadow-xl">
          {error && (
            <div className="p-3 text-xs text-red-300 bg-red-500/10">{error}</div>
          )}

          {!error && results.length === 0 && !loading && (
            <div className="p-4 text-xs text-inkMute text-center">
              No regulations matched "{q}"
            </div>
          )}

          {results.length > 0 && (
            <>
              <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-inkMute bg-panel2 border-b border-edge flex items-center justify-between">
                <span>{results.length} result{results.length === 1 ? '' : 's'}</span>
                <span className={clsx(
                  'px-1.5 py-0.5 rounded-md',
                  method === 'atlas_search' ? 'bg-accent/15 text-accent-soft' : 'bg-white/5 text-inkMute',
                )}>
                  {method === 'atlas_search' ? 'Atlas Search' : 'fallback'}
                </span>
              </div>
              <div>
                {results.map((r) => {
                  const catKey = r.category || 'other'
                  const catLabel = CATEGORY_LABELS[catKey] ?? catKey
                  const catTone = CATEGORY_TONES[catKey] ?? 'bg-white/5 text-inkMute'
                  return (
                    <div key={r._id} className="p-3 border-b border-edgeSoft last:border-b-0 hover:bg-white/5">
                      <div className="flex items-start gap-2">
                        <span className={clsx('text-[10px] font-bold px-1.5 py-0.5 rounded-md flex-shrink-0 mt-0.5', catTone)}>
                          {catLabel}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold text-ink leading-snug">{r.name}</p>
                          {r.deadline_rule && (
                            <p className="text-[10px] text-inkMute mt-0.5 truncate">{r.deadline_rule}</p>
                          )}
                          <div className="flex items-center gap-2 text-[10px] text-inkMute mt-1">
                            {r.frequency && <span>{r.frequency}</span>}
                            {r.state_specific && <span>· {r.state_specific}</span>}
                            <span>· max {formatINR(r.max_penalty_inr)}</span>
                            {r.score !== null && r.score !== undefined && (
                              <span className="ml-auto opacity-60">score {r.score.toFixed(2)}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
