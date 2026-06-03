import { useState, useEffect } from 'react'
import type { User } from 'firebase/auth'
import clsx from 'clsx'
import { signOutUser } from '../services/firebase'
import {
  getObligations,
  getFilingHistory,
  generateDraft,
  checkRipple,
  pingHealth,
  confirmObligation,
  dismissObligation,
  getExposure,
  getDecayTrend,
  getHealthScore,
  getExposureForecast,
  getBenchmark,
  subscribeToEvents,
  type ChangeStreamEvent,
  type ObligationInstance,
  type FilingHistory as FilingHistoryType,
  type DraftDocument,
  type RippleReport,
  type ExposureSummary,
  type DecayTrends,
  type HealthScore,
  type ExposureForecast as ExposureForecastType,
  type BenchmarkResponse,
} from '../services/api'
import HealthScoreRing from './HealthScoreRing'
import ExposureForecastCard from './ExposureForecastCard'
import BenchmarkCard from './BenchmarkCard'
import AutoDraftQueue from './AutoDraftQueue'
import FilingHistoryComp from './FilingHistory'
import AIAdvisorTab from './AIAdvisorTab'
import OverviewTab from './tabs/OverviewTab'
import ObligationsTab from './tabs/ObligationsTab'
import RippleTab from './tabs/RippleTab'
import ComplianceOfficerTab from './tabs/ComplianceOfficerTab'
import CalendarTab from './tabs/CalendarTab'
import CascadeTab from './tabs/CascadeTab'
import DecisionsTab from './tabs/DecisionsTab'
import RegulationSearch from './RegulationSearch'
import EditProfileModal from './EditProfileModal'
import ExplainRegulationModal from './ExplainRegulationModal'
import ProfilePage from './ProfilePage'
import { pushToast } from './Toaster'

interface DashboardProps {
  user: User
}

type Tab = 'overview' | 'officer' | 'obligations' | 'calendar' | 'ripple' | 'cascade' | 'documents' | 'history' | 'advisor' | 'audit' | 'profile'

function NavIcon({ id, className }: { id: Tab; className?: string }) {
  const cls = className ?? 'w-[18px] h-[18px]'
  const common = { fill: 'none' as const, viewBox: '0 0 24 24', stroke: 'currentColor', strokeWidth: 1.8 }
  switch (id) {
    case 'overview':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 5h6v6H4zM14 5h6v4h-6zM14 13h6v6h-6zM4 15h6v4H4z" /></svg>
    case 'officer':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 2l7 3v6c0 4.4-3 8.5-7 9.9C8 19.5 5 15.4 5 11V5l7-3z" /></svg>
    case 'obligations':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg>
    case 'calendar':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3M4 11h16M5 5h14a1 1 0 011 1v13a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z" /></svg>
    case 'ripple':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 12a3 3 0 100-6 3 3 0 000 6zM5 19c0-3 3-5 7-5s7 2 7 5M3.5 12a8.5 8.5 0 0117 0" /></svg>
    case 'cascade':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h6M14 6h6M9 12h6M4 18h6M14 18h6M7 6v6m10-6v6M12 12v6" /></svg>
    case 'documents':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 4H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
    case 'history':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M3 12a9 9 0 109-9 9 9 0 00-7 3.3M3 4v4h4M12 7v5l3 2" /></svg>
    case 'advisor':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.9 4.3L18 9l-4.1 1.7L12 15l-1.9-4.3L6 9l4.1-1.7L12 3zM18 14l.9 2.1L21 17l-2.1.9L18 20l-.9-2.1L15 17l2.1-.9L18 14z" /></svg>
    case 'audit':
      return <svg className={cls} {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2M9 12h.01M9 16h.01M13 12h3M13 16h3" /></svg>
    default:
      return null
  }
}

function SkeletonCard() {
  return (
    <div className="os-card p-5 animate-pulse">
      <div className="h-3 bg-white/10 rounded w-1/2 mb-3" />
      <div className="h-8 bg-white/10 rounded w-1/3 mb-2" />
      <div className="h-2.5 bg-white/5 rounded w-2/3" />
    </div>
  )
}

function SummaryCard({
  label, value, sub, color, accentBar,
}: { label: string; value: string | number; sub?: string; color: string; accentBar?: string }) {
  return (
    <div className="os-card os-card-hover p-5 relative overflow-hidden">
      {accentBar && <span className={clsx('absolute left-0 top-0 h-full w-1', accentBar)} />}
      <p className="text-[11px] font-semibold text-inkMute uppercase tracking-wider mb-2">{label}</p>
      <p className={clsx('text-3xl font-black tracking-tight', color)}>{value}</p>
      {sub && <p className="text-xs text-inkFaint mt-1">{sub}</p>}
    </div>
  )
}

export default function Dashboard({ user }: DashboardProps) {
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [obligations, setObligations] = useState<ObligationInstance[]>([])
  const [history, setHistory] = useState<FilingHistoryType[]>([])
  const [drafts, setDrafts] = useState<DraftDocument[]>([])
  const [rippleAlerts, setRippleAlerts] = useState<RippleReport[]>([])
  const [rippleLoading, setRippleLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [generatingDraft, setGeneratingDraft] = useState<string | null>(null)
  const [exposure, setExposure] = useState<ExposureSummary | null>(null)
  const [trends, setTrends] = useState<DecayTrends>({})
  const [editOpen, setEditOpen] = useState(false)
  const [healthScore, setHealthScore] = useState<HealthScore | null>(null)
  const [forecast, setForecast] = useState<ExposureForecastType | null>(null)
  const [benchmark, setBenchmark] = useState<BenchmarkResponse | null>(null)
  const [explainQuestion, setExplainQuestion] = useState<string | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [profileRefresh, setProfileRefresh] = useState(0)

  // Switch tab AND reset scroll, so each sidebar page opens at its own top
  // rather than leaving you scrolled into the previous page.
  function goToTab(tab: Tab) {
    setActiveTab(tab)
    setMobileNavOpen(false)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function explainObligation(name: string) {
    setExplainQuestion(`What is "${name}" — when is it due and what does it require?`)
  }

  const businessId = localStorage.getItem('business_id') ?? ''
  const businessName = localStorage.getItem('business_name') ?? 'Your Business'

  useEffect(() => {
    pingHealth()

    async function loadData() {
      setLoading(true)
      try {
        const [obs, hist, exp, tr, hs, fc, bm] = await Promise.all([
          getObligations(businessId),
          getFilingHistory(businessId),
          getExposure(businessId).catch(() => null),
          getDecayTrend(businessId).catch(() => ({})),
          getHealthScore(businessId).catch(() => null),
          getExposureForecast(businessId).catch(() => null),
          getBenchmark(businessId).catch(() => null),
        ])
        setObligations(obs)
        setHistory(hist)
        setExposure(exp)
        setTrends(tr)
        setHealthScore(hs)
        setForecast(fc)
        setBenchmark(bm)
      } finally {
        setLoading(false)
      }
    }
    if (businessId) loadData()
    else setLoading(false)
  }, [businessId])

  // Live MongoDB Change Streams → SSE → toasts
  useEffect(() => {
    if (!businessId) return
    const unsubscribe = subscribeToEvents(businessId, async (event: ChangeStreamEvent) => {
      if (event.kind === 'subscribed') return  // handshake — ignore

      if (event.collection === 'regulatory_changes' && event.operation === 'insert') {
        pushToast(
          `New ripple: "${event.title || 'regulation change'}" — ${event.direct_count ?? 0} direct, ${event.indirect_count ?? 0} indirect`,
          'info',
        )
        try {
          const [obs, exp] = await Promise.all([
            getObligations(businessId),
            getExposure(businessId).catch(() => null),
          ])
          setObligations(obs)
          if (exp) setExposure(exp)
        } catch { /* ignore */ }
      } else if (event.collection === 'obligation_instances' && event.operation === 'update') {
        const fields = event.changed_fields ?? []
        if (fields.includes('status') && event.urgency === 'red') {
          pushToast(`Obligation went RED: ${event.name}`, 'error')
        }
      } else if (event.collection === 'agent_decisions' && event.operation === 'insert') {
        const action = (event.action || '').replace(/_/g, ' ')
        if (action && action !== 'get obligations' && action !== 'get filing history') {
          pushToast(`Agent action: ${action}`, 'info')
        }
      }
    })
    return unsubscribe
  }, [businessId])

  function formatINR(n: number): string {
    if (n >= 10_000_000) return `${(n / 10_000_000).toFixed(2)}Cr`
    if (n >= 100_000) return `${(n / 100_000).toFixed(2)}L`
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
    return `${n}`
  }

  async function handleDraftClick(instanceId: string) {
    setGeneratingDraft(instanceId)
    try {
      const draft = await generateDraft(instanceId)
      setDrafts((prev) => {
        if (prev.find((d) => d.instance_id === instanceId)) return prev
        return [draft, ...prev]
      })
      setActiveTab('documents')
    } finally {
      setGeneratingDraft(null)
    }
  }

  function handleApprove(instanceId: string) {
    setDrafts((prev) => prev.filter((d) => d.instance_id !== instanceId))
  }

  async function handleConfirmObligation(instanceId: string) {
    await confirmObligation(instanceId)
    setObligations((prev) =>
      prev.map((o) => o.instance_id === instanceId ? { ...o, status: 'pending' as const } : o)
    )
  }

  async function handleDismissObligation(instanceId: string) {
    await dismissObligation(instanceId)
    setObligations((prev) => prev.filter((o) => o.instance_id !== instanceId))
  }

  async function handleRippleCheck(description: string, effectiveDate: string) {
    if (!businessId) return
    setRippleLoading(true)
    try {
      const report = await checkRipple(businessId, {
        regulation_id: `custom-${Date.now()}`,
        change_type: 'amendment',
        description,
        effective_date: effectiveDate,
      })
      setRippleAlerts((prev) => [report, ...prev])
      setActiveTab('ripple')
    } finally {
      setRippleLoading(false)
    }
  }

  const highSeverity = obligations.filter((o) => o.decay_score < 20).length
  const dueThisWeek = obligations.filter((o) => {
    const d = new Date(o.deadline)
    const diff = (d.getTime() - Date.now()) / (1000 * 60 * 60 * 24)
    return diff >= 0 && diff <= 7
  }).length
  const total = history.length
  const onTime = history.filter((h) => h.status === 'on_time').length
  const onTimeRate = total > 0 ? `${Math.round((onTime / total) * 100)}%` : '—'

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'officer', label: 'Compliance Officer' },
    { id: 'obligations', label: 'Obligations', count: obligations.length },
    { id: 'calendar', label: 'Calendar' },
    { id: 'ripple', label: 'Ripple Alerts', count: rippleAlerts.length || undefined },
    { id: 'cascade', label: 'Cascade Demo' },
    { id: 'documents', label: 'Documents', count: drafts.length || undefined },
    { id: 'history', label: 'History' },
    { id: 'advisor', label: 'AI Advisor' },
    { id: 'audit', label: 'Audit Log' },
  ]

  const activeLabel = activeTab === 'profile'
    ? 'Profile'
    : tabs.find((t) => t.id === activeTab)?.label ?? 'Overview'

  return (
    <div className="min-h-screen bg-canvas text-ink">
      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 w-64 bg-panel border-r border-edge flex flex-col',
          'transition-transform duration-200 lg:translate-x-0',
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Brand */}
        <div className="h-16 flex items-center gap-2.5 px-5 border-b border-edge">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shadow-glow">
            <svg className="w-5 h-5 text-canvas" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <span className="font-bold text-ink text-[15px] tracking-tight">ComplianceOS</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-inkFaint px-3 mb-2">Workspace</p>
          {tabs.map((tab) => {
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => goToTab(tab.id)}
                className={clsx(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors relative',
                  active
                    ? 'bg-accent/10 text-accent-soft'
                    : 'text-inkMute hover:text-ink hover:bg-white/5',
                )}
              >
                {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent" />}
                <NavIcon id={tab.id} className={clsx('w-[18px] h-[18px]', active ? 'text-accent-soft' : 'text-inkFaint')} />
                <span className="flex-1 text-left truncate">{tab.label}</span>
                {tab.count !== undefined && tab.count > 0 && (
                  <span className={clsx(
                    'text-[11px] px-1.5 py-0.5 rounded-full font-semibold',
                    active ? 'bg-accent/20 text-accent-soft' : 'bg-white/5 text-inkMute',
                  )}>
                    {tab.count}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* User card */}
        <div className="border-t border-edge p-3">
          <div className="flex items-center gap-2.5 px-2 py-2">
            {user.photoURL
              ? <img src={user.photoURL} alt="" className="w-8 h-8 rounded-full ring-1 ring-edge" />
              : <div className="w-8 h-8 rounded-full bg-panel2 flex items-center justify-center text-xs font-bold text-inkMute">{businessName.charAt(0)}</div>}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-ink truncate">{businessName}</p>
              <p className="text-[11px] text-inkFaint truncate">{user.email}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2">
            <button
              onClick={() => goToTab('profile')}
              className={clsx(
                'text-xs px-2 py-1.5 flex items-center justify-center gap-1.5 rounded-lg border transition-colors',
                activeTab === 'profile'
                  ? 'bg-accent/10 text-accent-soft border-accent/40'
                  : 'os-btn-ghost',
              )}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Profile
            </button>
            <button
              onClick={() => { signOutUser(); localStorage.clear(); window.location.href = '/login' }}
              className="os-btn-ghost text-xs px-2 py-1.5 flex items-center justify-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={() => setMobileNavOpen(false)} />
      )}

      {/* ── Main column ──────────────────────────────────────────────────── */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-20 h-16 bg-canvas/80 backdrop-blur-md border-b border-edge flex items-center gap-3 px-4 sm:px-6">
          <button
            onClick={() => setMobileNavOpen(true)}
            className="lg:hidden os-btn-ghost p-2"
            aria-label="Open navigation"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="min-w-0">
            <h1 className="text-base font-bold text-ink leading-none truncate">{activeLabel}</h1>
            <p className="text-[11px] text-inkFaint mt-1 truncate">{businessName} · real-time compliance monitoring</p>
          </div>
          <div className="ml-auto">
            <RegulationSearch />
          </div>
        </header>

        <main className="px-4 sm:px-6 py-6 space-y-6 max-w-[1400px]">
          {/* Summary widgets live on the Overview page only — every other
              sidebar item leads with its own content. */}
          {activeTab === 'overview' && (
          <div className="space-y-6">
          {/* Health ring */}
          {(healthScore || loading) && (
            <HealthScoreRing data={healthScore} loading={loading && !healthScore} />
          )}

          {/* Total ₹ exposure banner */}
          {exposure && exposure.total_pending > 0 && (
            <div className="rounded-2xl p-5 flex items-center justify-between flex-wrap gap-4 border border-red-500/30 bg-red-500/[0.06]">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wider text-red-400">Total Penalty Exposure</p>
                <p className="text-4xl font-black text-red-300 mt-1 tracking-tight">
                  ₹{formatINR(exposure.total_exposure_inr)}
                </p>
                <p className="text-xs text-inkMute mt-1">
                  across {exposure.total_pending} pending obligations · what you'd owe if you missed every deadline
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs">
                {(['red', 'amber', 'green'] as const).map((band) => {
                  const bucket = exposure.by_urgency[band]
                  if (!bucket || bucket.count === 0) return null
                  const labels: Record<typeof band, string> = { red: 'Urgent', amber: 'Warning', green: 'On Track' }
                  const tones: Record<typeof band, string> = {
                    red: 'bg-red-500/10 text-red-300 border-red-500/30',
                    amber: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
                    green: 'bg-accent/10 text-accent-soft border-accent/30',
                  }
                  return (
                    <div key={band} className={clsx('px-3 py-2 border rounded-xl text-center min-w-[80px]', tones[band])}>
                      <p className="text-[10px] font-bold uppercase">{labels[band]}</p>
                      <p className="text-lg font-black">{bucket.count}</p>
                      <p className="text-[10px] opacity-80">₹{formatINR(bucket.max_penalty_total)}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Forecast + benchmark */}
          {(forecast || loading) && (
            <ExposureForecastCard data={forecast} loading={loading && !forecast} />
          )}
          {(benchmark || loading) && (
            <BenchmarkCard data={benchmark} loading={loading && !benchmark} />
          )}

          {/* KPI summary cards */}
          {loading ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <SummaryCard label="Total Obligations" value={obligations.length || '—'}
                sub="Active compliance items" color="text-ink" accentBar="bg-accent" />
              <SummaryCard label="High Severity" value={highSeverity}
                sub="Score below 20"
                color={highSeverity > 0 ? 'text-red-400' : 'text-accent-soft'}
                accentBar={highSeverity > 0 ? 'bg-red-500' : 'bg-accent'} />
              <SummaryCard label="Due This Week" value={dueThisWeek}
                sub="Within 7 days"
                color={dueThisWeek > 0 ? 'text-amber-400' : 'text-accent-soft'}
                accentBar={dueThisWeek > 0 ? 'bg-amber-500' : 'bg-accent'} />
              <SummaryCard label="On-Time Rate" value={onTimeRate}
                sub={`${onTime} of ${total} filings`}
                color={
                  onTimeRate === '—' ? 'text-inkFaint'
                  : parseInt(onTimeRate) >= 80 ? 'text-accent-soft'
                  : parseInt(onTimeRate) >= 60 ? 'text-amber-400'
                  : 'text-red-400'
                }
                accentBar={
                  onTimeRate === '—' ? 'bg-edge'
                  : parseInt(onTimeRate) >= 80 ? 'bg-accent'
                  : parseInt(onTimeRate) >= 60 ? 'bg-amber-500'
                  : 'bg-red-500'
                } />
            </div>
          )}
          </div>
          )}

          {/* Active tab content */}
          <div className="min-h-64">
            {activeTab === 'overview' && (
              <OverviewTab
                obligations={obligations}
                rippleAlerts={rippleAlerts}
                loading={loading}
                onDraftClick={handleDraftClick}
                onRippleCheck={handleRippleCheck}
                rippleLoading={rippleLoading}
                trends={trends}
                onExplainClick={explainObligation}
              />
            )}
            {activeTab === 'officer' && (
              <ComplianceOfficerTab businessId={businessId} businessName={businessName} />
            )}
            {activeTab === 'calendar' && (
              <CalendarTab obligations={obligations} onDraftClick={handleDraftClick} />
            )}
            {activeTab === 'obligations' && (
              <ObligationsTab
                obligations={obligations}
                loading={loading}
                onDraftClick={handleDraftClick}
                onConfirm={handleConfirmObligation}
                onDismiss={handleDismissObligation}
                trends={trends}
                onExplainClick={explainObligation}
              />
            )}
            {activeTab === 'ripple' && (
              <RippleTab alerts={rippleAlerts} onCheck={handleRippleCheck} loading={rippleLoading} />
            )}
            {activeTab === 'cascade' && (
              <CascadeTab />
            )}
            {activeTab === 'documents' && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-ink">Auto-Generated Draft Queue</h3>
                  <span className="text-xs text-inkMute os-chip px-2.5 py-1">
                    {drafts.length} pending review
                  </span>
                </div>
                <div className="os-panel p-6">
                  <AutoDraftQueue drafts={drafts} onApprove={handleApprove} />
                </div>
              </div>
            )}
            {activeTab === 'history' && <FilingHistoryComp history={history} />}
            {activeTab === 'advisor' && (
              <AIAdvisorTab
                businessId={businessId}
                businessName={businessName}
                onGoToObligations={() => setActiveTab('obligations')}
              />
            )}
            {activeTab === 'audit' && (
              <DecisionsTab businessId={businessId} />
            )}
            {activeTab === 'profile' && (
              <ProfilePage
                user={user}
                businessId={businessId}
                refreshSignal={profileRefresh}
                onEdit={() => setEditOpen(true)}
                onSignOut={() => { signOutUser(); localStorage.clear(); window.location.href = '/login' }}
              />
            )}
          </div>
        </main>
      </div>

      {generatingDraft && (
        <div className="fixed bottom-6 right-6 os-card bg-panel2 text-ink px-4 py-3 shadow-glow flex items-center gap-2.5 text-sm z-50">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          Generating draft document…
        </div>
      )}

      <ExplainRegulationModal
        open={!!explainQuestion}
        onClose={() => setExplainQuestion(null)}
        businessId={businessId}
        initialQuestion={explainQuestion ?? undefined}
      />

      <EditProfileModal
        businessId={businessId}
        open={editOpen}
        onClose={() => setEditOpen(false)}
        onSaved={() => {
          setProfileRefresh((n) => n + 1)
          if (businessId) {
            Promise.all([
              getObligations(businessId),
              getExposure(businessId).catch(() => null),
            ]).then(([obs, exp]) => {
              setObligations(obs)
              if (exp) setExposure(exp)
            })
          }
        }}
      />
    </div>
  )
}
