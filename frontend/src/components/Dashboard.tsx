import { useState, useEffect } from 'react'
import type { User } from 'firebase/auth'
import { signOutUser } from '../services/firebase'
import {
  getObligations,
  getFilingHistory,
  generateDraft,
  type ObligationInstance,
  type FilingHistory as FilingHistoryType,
  type DraftDocument,
  type RippleReport,
} from '../services/api'
import DecayScoreCard from './DecayScoreCard'
import RippleAlertCard from './RippleAlertCard'
import AutoDraftQueue from './AutoDraftQueue'
import FilingHistoryComp from './FilingHistory'
import clsx from 'clsx'

interface DashboardProps {
  user: User
}

type Tab = 'overview' | 'obligations' | 'ripple' | 'documents' | 'history'

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 animate-pulse shadow-sm">
      <div className="h-4 bg-gray-200 rounded w-1/2 mb-3" />
      <div className="h-8 bg-gray-200 rounded w-1/3 mb-2" />
      <div className="h-3 bg-gray-100 rounded w-2/3" />
    </div>
  )
}

function SummaryCard({
  label, value, sub, color,
}: { label: string; value: string | number; sub?: string; color: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm hover:shadow-md transition-shadow">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{label}</p>
      <p className={clsx('text-3xl font-black', color)}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

// Mock ripple alerts — replace with real API when available
const MOCK_RIPPLE: RippleReport[] = [
  {
    change_title: 'GST Annual Return (GSTR-9) — Threshold for Audit Reconciliation Revised',
    effective_date: '2025-04-01',
    direct_impacts: [
      {
        obligation_id: '1',
        obligation_name: 'GSTR-9 Annual Return',
        impact_type: 'direct',
        description: 'New turnover threshold of ₹2Cr now applies',
      },
    ],
    indirect_impacts: [
      {
        obligation_id: '2',
        obligation_name: 'GSTR-1 Monthly Return',
        impact_type: 'indirect',
        description: 'Reconciliation with GSTR-9 may be affected',
      },
    ],
    total_affected: 2,
    severity: 'high',
  },
  {
    change_title: 'EPF Wage Ceiling Enhanced — EPFO Circular 2025',
    effective_date: '2025-06-01',
    direct_impacts: [
      {
        obligation_id: '3',
        obligation_name: 'EPF Monthly Contribution',
        impact_type: 'direct',
        description: 'New wage ceiling increases monthly contribution amount',
      },
    ],
    indirect_impacts: [],
    total_affected: 1,
    severity: 'medium',
  },
]

export default function Dashboard({ user }: DashboardProps) {
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [obligations, setObligations] = useState<ObligationInstance[]>([])
  const [history, setHistory] = useState<FilingHistoryType[]>([])
  const [drafts, setDrafts] = useState<DraftDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [generatingDraft, setGeneratingDraft] = useState<string | null>(null)

  const businessId = localStorage.getItem('business_id') ?? ''
  const businessName = localStorage.getItem('business_name') ?? 'Your Business'

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      try {
        const [obs, hist] = await Promise.all([
          getObligations(businessId),
          getFilingHistory(businessId),
        ])
        setObligations(obs)
        setHistory(hist)
      } catch {
        // In demo mode, use empty arrays — API may not be running
      } finally {
        setLoading(false)
      }
    }
    if (businessId) loadData()
    else setLoading(false)
  }, [businessId])

  async function handleDraftClick(instanceId: string) {
    setGeneratingDraft(instanceId)
    try {
      const draft = await generateDraft(instanceId)
      setDrafts((prev) => {
        const exists = prev.find((d) => d.instance_id === instanceId)
        if (exists) return prev
        return [draft, ...prev]
      })
      setActiveTab('documents')
    } catch {
      // handle silently for now
    } finally {
      setGeneratingDraft(null)
    }
  }

  function handleApprove(instanceId: string) {
    setDrafts((prev) => prev.filter((d) => d.instance_id !== instanceId))
  }

  // Derived stats
  const highSeverity = obligations.filter((o) => o.decay_score < 20).length
  const dueThisWeek = obligations.filter((o) => {
    const d = new Date(o.deadline)
    const now = new Date()
    const diff = (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
    return diff >= 0 && diff <= 7
  }).length
  const total = history.length
  const onTime = history.filter((h) => h.status === 'on_time').length
  const onTimeRate = total > 0 ? `${Math.round((onTime / total) * 100)}%` : '—'

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'obligations', label: 'Obligations', count: obligations.length },
    { id: 'ripple', label: 'Ripple Alerts', count: MOCK_RIPPLE.length },
    { id: 'documents', label: 'Documents', count: drafts.length || undefined },
    { id: 'history', label: 'History' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-30 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="font-bold text-gray-900 text-lg">ComplianceOS</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2">
              {user.photoURL && (
                <img src={user.photoURL} alt="" className="w-7 h-7 rounded-full" />
              )}
              <span className="text-sm font-medium text-gray-700">{businessName}</span>
            </div>
            <button
              onClick={() => {
                signOutUser()
                localStorage.clear()
                window.location.href = '/login'
              }}
              className="text-xs font-medium px-3 py-1.5 text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg hover:bg-gray-50 transition-all"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Page title */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Compliance Dashboard</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {businessName} · Real-time compliance monitoring
          </p>
        </div>

        {/* Summary Cards */}
        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <SummaryCard
              label="Total Obligations"
              value={obligations.length || '—'}
              sub="Active compliance items"
              color="text-gray-900"
            />
            <SummaryCard
              label="High Severity"
              value={highSeverity}
              sub="Score below 20"
              color={highSeverity > 0 ? 'text-red-600' : 'text-green-600'}
            />
            <SummaryCard
              label="Due This Week"
              value={dueThisWeek}
              sub="Within 7 days"
              color={dueThisWeek > 0 ? 'text-amber-600' : 'text-green-600'}
            />
            <SummaryCard
              label="On-Time Rate"
              value={onTimeRate}
              sub={`${onTime} of ${total} filings`}
              color={
                onTimeRate === '—' ? 'text-gray-400'
                : parseInt(onTimeRate) >= 80 ? 'text-green-600'
                : parseInt(onTimeRate) >= 60 ? 'text-amber-600'
                : 'text-red-600'
              }
            />
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 bg-white rounded-xl border border-gray-100 p-1 shadow-sm overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap',
                activeTab === tab.id
                  ? 'bg-green-500 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              )}
            >
              {tab.label}
              {tab.count !== undefined && tab.count > 0 && (
                <span className={clsx(
                  'text-xs px-1.5 py-0.5 rounded-full font-semibold',
                  activeTab === tab.id
                    ? 'bg-white/20 text-white'
                    : 'bg-gray-100 text-gray-600'
                )}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="min-h-64">
          {activeTab === 'overview' && (
            <OverviewTab
              obligations={obligations}
              rippleAlerts={MOCK_RIPPLE}
              loading={loading}
              onDraftClick={handleDraftClick}
              generatingDraft={generatingDraft}
            />
          )}
          {activeTab === 'obligations' && (
            <ObligationsTab
              obligations={obligations}
              loading={loading}
              onDraftClick={handleDraftClick}
              generatingDraft={generatingDraft}
            />
          )}
          {activeTab === 'ripple' && (
            <div className="space-y-4">
              <h3 className="font-semibold text-gray-800">Regulatory Change Alerts</h3>
              {MOCK_RIPPLE.map((r, i) => (
                <RippleAlertCard key={i} {...r} />
              ))}
            </div>
          )}
          {activeTab === 'documents' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-800">Auto-Generated Draft Queue</h3>
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                  {drafts.length} pending review
                </span>
              </div>
              <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                <AutoDraftQueue drafts={drafts} onApprove={handleApprove} />
              </div>
            </div>
          )}
          {activeTab === 'history' && (
            <FilingHistoryComp history={history} />
          )}
        </div>
      </main>

      {/* Generating draft overlay feedback */}
      {generatingDraft && (
        <div className="fixed bottom-6 right-6 bg-gray-900 text-white px-4 py-3 rounded-xl shadow-lg flex items-center gap-2.5 text-sm z-50">
          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          Generating draft document…
        </div>
      )}
    </div>
  )
}

// ─── Sub-views ────────────────────────────────────────────────────────────────

function OverviewTab({
  obligations,
  rippleAlerts,
  loading,
  onDraftClick,
  generatingDraft: _generatingDraft,
}: {
  obligations: ObligationInstance[]
  rippleAlerts: RippleReport[]
  loading: boolean
  onDraftClick: (id: string) => void
  generatingDraft: string | null
}) {
  const urgent = obligations.filter((o) => o.decay_score < 20).slice(0, 3)
  const warning = obligations.filter((o) => o.decay_score >= 20 && o.decay_score <= 40).slice(0, 3)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left: urgent obligations */}
      <div className="lg:col-span-2 space-y-4">
        <h3 className="font-semibold text-gray-800">Urgent Attention Required</h3>
        {loading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-100 p-5 animate-pulse h-24" />
            ))}
          </div>
        ) : urgent.length === 0 && warning.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-100 p-8 text-center shadow-sm">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="font-semibold text-gray-700">All obligations on track</p>
            <p className="text-xs text-gray-400 mt-1">No urgent items at this time</p>
          </div>
        ) : (
          <div className="space-y-3">
            {[...urgent, ...warning].map((o) => (
              <DecayScoreCard
                key={o.instance_id}
                {...o}
                onDraftClick={onDraftClick}
              />
            ))}
          </div>
        )}
      </div>

      {/* Right: ripple alerts */}
      <div className="space-y-4">
        <h3 className="font-semibold text-gray-800">Recent Ripple Alerts</h3>
        {rippleAlerts.slice(0, 2).map((r, i) => (
          <RippleAlertCard key={i} {...r} />
        ))}
      </div>
    </div>
  )
}

function ObligationsTab({
  obligations,
  loading,
  onDraftClick,
  generatingDraft: _generatingDraft,
}: {
  obligations: ObligationInstance[]
  loading: boolean
  onDraftClick: (id: string) => void
  generatingDraft: string | null
}) {
  const [filter, setFilter] = useState<'all' | 'urgent' | 'warning' | 'on_track'>('all')

  const filtered = obligations.filter((o) => {
    if (filter === 'urgent') return o.decay_score < 20
    if (filter === 'warning') return o.decay_score >= 20 && o.decay_score <= 40
    if (filter === 'on_track') return o.decay_score > 40
    return true
  })

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {[
          { id: 'all', label: 'All', count: obligations.length },
          { id: 'urgent', label: 'Urgent', count: obligations.filter((o) => o.decay_score < 20).length },
          { id: 'warning', label: 'Warning', count: obligations.filter((o) => o.decay_score >= 20 && o.decay_score <= 40).length },
          { id: 'on_track', label: 'On Track', count: obligations.filter((o) => o.decay_score > 40).length },
        ].map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id as typeof filter)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all',
              filter === f.id
                ? 'bg-gray-900 text-white border-gray-900'
                : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
            )}
          >
            {f.label} ({f.count})
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 p-5 animate-pulse h-24" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-sm font-medium">No obligations in this category</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((o) => (
            <DecayScoreCard
              key={o.instance_id}
              {...o}
              onDraftClick={onDraftClick}
            />
          ))}
        </div>
      )}
    </div>
  )
}
