import axios from 'axios'
import { auth } from './firebase'

const RAW_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
// Always talk to the versioned API. If the env var already ends in /api/v1
// (e.g. when running behind a gateway), don't double-prefix.
const BASE_URL = RAW_BASE.replace(/\/+$/, '').endsWith('/api/v1')
  ? RAW_BASE.replace(/\/+$/, '')
  : `${RAW_BASE.replace(/\/+$/, '')}/api/v1`

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach the Firebase ID token to every request. Backend treats it as
// optional unless REQUIRE_AUTH=true, but sending it always means the
// hardening flip is a one-env-var change with zero frontend work.
api.interceptors.request.use(async (cfg) => {
  const user = auth.currentUser
  if (user) {
    try {
      const token = await user.getIdToken()
      cfg.headers.Authorization = `Bearer ${token}`
    } catch {
      // Token fetch can fail offline — proceed unauth and let the backend decide.
    }
  }
  return cfg
})

// Centralise error messaging so toasts can subscribe.
export type ApiNoticeKind = 'error' | 'info'
type ErrListener = (msg: string, kind: ApiNoticeKind) => void
const errListeners = new Set<ErrListener>()
export function onApiError(fn: ErrListener): () => void {
  errListeners.add(fn)
  return () => errListeners.delete(fn)
}
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    const msg = typeof detail === 'string'
      ? detail
      : status ? `Request failed (${status})` : 'Network error — backend unreachable'
    // Gemini limits/overloads (429 quota, 503 high-demand) are expected external
    // conditions, not app errors — surface them as calm info notices, not red.
    const isTransientLLM = status === 429 || status === 503
      || /quota|rate.?limit|unavailable|overloaded|high demand/i.test(msg)
    // Health pings stay silent so cold-start doesn't fire a toast.
    if (!String(err?.config?.url ?? '').endsWith('/health')) {
      errListeners.forEach((fn) => fn(msg, isTransientLLM ? 'info' : 'error'))
    }
    return Promise.reject(err)
  },
)

// ─── TypeScript Interfaces ───────────────────────────────────────────────────

export interface BusinessProfile {
  business_name: string
  owner_name: string
  business_type: 'proprietorship' | 'partnership' | 'pvt_ltd' | 'llp'
  state: string
  industry: string
  employee_count: number
  annual_turnover_inr: number
  registrations: string[]
}

export interface DNASummary {
  total_obligations: number
  high_priority: number
  frameworks: string[]
  risk_score: number
  created_at: string
}

export interface ObligationInstance {
  instance_id: string
  obligation_name: string
  framework: string
  deadline: string
  decay_score: number
  predicted_penalty_inr: number
  status: 'pending' | 'in_progress' | 'filed' | 'overdue' | 'proposed'
  period: string
  description: string
}

export interface RegChange {
  regulation_id: string
  change_type: string
  description: string
  effective_date: string
}

export interface RippleImpact {
  obligation_name: string
  obligation_id: string
  impact_type: 'direct' | 'indirect'
  description: string
}

export interface RippleReport {
  change_title: string
  effective_date: string
  direct_impacts: RippleImpact[]
  indirect_impacts: RippleImpact[]
  total_affected: number
  severity: 'high' | 'medium' | 'low'
}

export interface PenaltyPreview {
  instance_id: string
  obligation_name: string
  base_penalty_inr: number
  per_day_penalty_inr: number
  estimated_days_late: number
  total_estimated_penalty_inr: number
  is_first_offense: boolean
  penalty_breakdown: string
}

export interface AdvisorNotes {
  documents_required: string[]
  common_mistakes: string[]
  risk_level: 'low' | 'medium' | 'high'
  risk_reason: string
  filing_checklist: string[]
}

export interface DraftDocument {
  instance_id: string
  obligation_name: string
  period: string
  pre_filled_fields: Record<string, string>
  fields_count: number
  document_type: string
  status: 'pending_review' | 'approved' | 'filed'
  generated_at: string
  advisor_notes?: AdvisorNotes
}

export interface FilingHistory {
  filing_id: string
  obligation_name: string
  period: string
  filed_date: string | null
  deadline: string
  days_late: number
  penalty_paid_inr: number
  status: 'on_time' | 'late' | 'pending'
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface DiscoveredObligation {
  name: string
  reason: string
  category: string
  urgency: 'immediate' | 'next_30_days' | 'annual'
}

export interface ChatDiscoverResponse {
  reply: string
  discovered: DiscoveredObligation[]
  suggestions: string[]
  business_facts: Record<string, unknown>
}

export interface ChatDiscovery {
  _id: string
  business_id: string
  obligation_name: string
  reason: string
  category: string
  urgency: 'immediate' | 'next_30_days' | 'annual'
  discovered_at: string
}

export interface CircularKeyChange {
  change: string
  effective_date: string
  action_required: string
}

export interface CircularInterpretResponse {
  plain_summary: string
  affected_business_types: string[]
  key_changes: CircularKeyChange[]
  applies_to_this_business: boolean
  reason: string
  urgency: 'high' | 'medium' | 'low'
  affected_categories: string[]
}

// ─── Score Color Utility ─────────────────────────────────────────────────────

export function getScoreColor(score: number): 'red' | 'amber' | 'green' {
  if (score < 20) return 'red'
  if (score <= 40) return 'amber'
  return 'green'
}

export function getScoreTailwind(score: number) {
  if (score < 20) return { border: 'border-red-500', text: 'text-red-400', bg: 'bg-red-500/10', badge: 'bg-red-500/15 text-red-300' }
  if (score <= 40) return { border: 'border-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/10', badge: 'bg-amber-500/15 text-amber-300' }
  return { border: 'border-accent', text: 'text-accent-soft', bg: 'bg-accent/10', badge: 'bg-accent/15 text-accent-soft' }
}

// ─── Response Transformers ───────────────────────────────────────────────────

function deadlineFallback(daysFromNow = 30): string {
  const d = new Date()
  d.setDate(d.getDate() + daysFromNow)
  return d.toISOString()
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function transformObligation(raw: any): ObligationInstance {
  const freqToDays: Record<string, number> = {
    daily: 1, weekly: 7, monthly: 30, quarterly: 90,
    half_yearly: 182, annual: 365, one_time: 365,
  }
  const daysAllowed = freqToDays[raw.frequency] ?? 30
  return {
    instance_id: raw._id ?? raw.instance_id ?? '',
    obligation_name: raw.name ?? raw.obligation_name ?? '',
    framework: raw.category ?? raw.framework ?? '',
    deadline: raw.due_date ?? deadlineFallback(daysAllowed),
    decay_score: Math.round(raw.decay_score ?? 50),
    predicted_penalty_inr: raw.max_penalty_inr ?? raw.predicted_penalty_inr ?? 0,
    status: raw.status ?? 'pending',
    period: raw.frequency ?? raw.period ?? 'monthly',
    description: raw.deadline_rule ?? raw.description ?? '',
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function transformFilingHistory(raw: any): FilingHistory {
  const filedAt = raw.filed_at ?? null
  const dueDate = raw.due_date ?? null

  let daysLate = 0
  if (filedAt && dueDate) {
    const diff = (new Date(filedAt).getTime() - new Date(dueDate).getTime()) / 86400000
    daysLate = diff > 0 ? Math.ceil(diff) : 0
  }

  const status: FilingHistory['status'] = raw.on_time === true
    ? 'on_time'
    : filedAt ? 'late' : 'pending'

  const snapshotName: string =
    raw.draft_snapshot?.template_name ??
    raw.regulation_id ??
    'Filing'

  return {
    filing_id: raw._id ?? '',
    obligation_name: snapshotName,
    period: filedAt
      ? new Date(filedAt).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
      : '—',
    filed_date: filedAt ?? null,
    deadline: dueDate ?? deadlineFallback(0),
    days_late: daysLate,
    penalty_paid_inr: 0,
    status,
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function transformDraft(raw: any): DraftDocument {
  const fields = raw.populated_fields ?? raw.pre_filled_fields ?? {}
  return {
    instance_id: raw.instance_id ?? '',
    obligation_name: raw.template_name ?? raw.obligation_name ?? 'Document',
    period: new Date().toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }),
    pre_filled_fields: fields,
    fields_count: Object.keys(fields).length,
    document_type: raw.output_format ?? raw.document_type ?? 'pdf',
    status: raw.status ?? 'pending_review',
    generated_at: raw.generated_at ?? new Date().toISOString(),
    advisor_notes: raw.advisor_notes ?? undefined,
  }
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function pingHealth(): Promise<void> {
  try {
    await api.get('/health', { timeout: 8000 })
  } catch {
    // silent — purpose is to wake Railway, not to surface errors
  }
}

export async function createBusiness(
  data: BusinessProfile & { incorporation_date?: string }
): Promise<{ business_id: string; dna: DNASummary }> {
  const res = await api.post('/business', {
    name: data.business_name,
    owner: data.owner_name,
    state: data.state,
    industry: data.industry,
    business_type: data.business_type,
    employee_count: data.employee_count,
    annual_turnover_inr: data.annual_turnover_inr,
    registrations: data.registrations,
    incorporation_date: data.incorporation_date || null,
  })
  const raw = res.data
  return {
    business_id: raw.business_id,
    dna: {
      total_obligations: raw.dna_summary?.total_obligations ?? 0,
      high_priority: raw.dna_summary?.high_severity_count ?? 0,
      frameworks: [],
      risk_score: 0,
      created_at: new Date().toISOString(),
    },
  }
}

export async function getObligations(
  businessId: string
): Promise<ObligationInstance[]> {
  const res = await api.get(`/obligations/${businessId}`)
  const raw = res.data
  const obligations = Array.isArray(raw) ? raw : (raw.obligations ?? [])
  return obligations.map(transformObligation)
}

function _inferCategories(description: string): string[] {
  const d = description.toLowerCase()
  const cats: string[] = []
  if (d.includes('gst') || d.includes('tax') || d.includes('tds') || d.includes('itc')) cats.push('taxation')
  if (d.includes('epf') || d.includes('pf') || d.includes('esi') || d.includes('labour') || d.includes('employee')) cats.push('labour')
  if (d.includes('fssai') || d.includes('food') || d.includes('safety')) cats.push('food_safety')
  if (d.includes('shop') || d.includes('establishment')) cats.push('shops_establishments')
  if (d.includes('companies act') || d.includes('mca') || d.includes('roc')) cats.push('companies_act')
  if (d.includes('income tax') || d.includes('itr')) cats.push('income_tax')
  return cats.length > 0 ? cats : ['taxation']
}

export async function checkRipple(
  businessId: string,
  change: RegChange
): Promise<RippleReport> {
  const res = await api.post('/regulations/check-ripple', {
    business_id: businessId,
    regulation_change: {
      title: change.description,
      affected_categories: _inferCategories(change.description),
      affected_registrations: [],
      severity: 'medium',
      effective_date: change.effective_date,
    },
  })
  const raw = res.data.ripple_report ?? {}
  const directImpacts: RippleImpact[] = (raw.directly_impacted ?? []).map(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (o: any): RippleImpact => ({
      obligation_id: o._id ?? o.instance_id ?? '',
      obligation_name: o.name ?? '',
      impact_type: 'direct',
      description: `${o.category} obligation affected`,
    })
  )
  const indirectImpacts: RippleImpact[] = (raw.indirectly_impacted ?? []).map(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (o: any): RippleImpact => ({
      obligation_id: o._id ?? o.instance_id ?? '',
      obligation_name: o.name ?? '',
      impact_type: 'indirect',
      description: `Dependency chain from ${o.category}`,
    })
  )
  return {
    change_title: change.description,
    effective_date: change.effective_date,
    direct_impacts: directImpacts,
    indirect_impacts: indirectImpacts,
    total_affected: raw.total_impacted ?? 0,
    severity: raw.severity ?? 'medium',
  }
}

export async function getPenaltyPreview(
  instanceId: string
): Promise<PenaltyPreview> {
  const res = await api.get(`/penalty-preview/${instanceId}`)
  const raw = res.data
  return {
    instance_id: raw.instance_id,
    obligation_name: raw.name ?? '',
    base_penalty_inr: raw.base_penalty_inr ?? 0,
    per_day_penalty_inr: raw.per_day_late_inr ?? 0,
    estimated_days_late: raw.projected_days_late ?? 0,
    total_estimated_penalty_inr: raw.predicted_penalty_inr ?? 0,
    is_first_offense: (raw.times_missed_before ?? 0) === 0,
    penalty_breakdown: `Base ₹${raw.base_penalty_inr ?? 0} + ₹${raw.per_day_late_inr ?? 0}/day`,
  }
}

export async function generateDraft(
  instanceId: string
): Promise<DraftDocument> {
  const res = await api.post(`/draft/${instanceId}`)
  return transformDraft(res.data)
}

export async function approveDraft(
  instanceId: string
): Promise<{ status: string }> {
  const res = await api.post(`/approve-draft/${instanceId}`, {})
  return { status: res.data.status ?? 'filed' }
}

export async function downloadDraftPdf(instanceId: string, suggestedName?: string): Promise<void> {
  const res = await api.get(`/draft/${instanceId}/pdf`, { responseType: 'blob' })
  const blob = new Blob([res.data], { type: 'application/pdf' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = suggestedName || `compliance-draft-${instanceId}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function confirmObligations(
  businessId: string,
  keepIds: string[],
  dueDates: Record<string, string>
): Promise<{ kept: number; removed: number }> {
  const res = await api.post(`/business/${businessId}/confirm-obligations`, {
    keep_ids: keepIds,
    due_dates: dueDates,
  })
  return res.data
}

export async function chatDiscover(
  businessId: string,
  messages: ChatMessage[],
  businessFacts: Record<string, unknown> = {},
  summarise = false,
): Promise<ChatDiscoverResponse> {
  const res = await api.post('/chat/discover', {
    business_id: businessId,
    messages,
    business_facts: businessFacts,
    summarise,
  })
  return res.data
}

export async function getChatDiscoveries(businessId: string): Promise<ChatDiscovery[]> {
  const res = await api.get(`/chat-discoveries/${businessId}`)
  return res.data.discoveries ?? []
}

export async function interpretCircular(
  businessId: string,
  circularText: string,
  circularSource: string,
): Promise<CircularInterpretResponse> {
  const res = await api.post('/circular/interpret', {
    business_id: businessId,
    circular_text: circularText,
    circular_source: circularSource,
  })
  return res.data
}

export async function confirmObligation(instanceId: string): Promise<{ status: string }> {
  const res = await api.post(`/obligations/${instanceId}/confirm`)
  return res.data
}

export async function dismissObligation(instanceId: string): Promise<{ status: string }> {
  const res = await api.delete(`/obligations/${instanceId}/dismiss`)
  return res.data
}

export async function getFilingHistory(
  businessId: string
): Promise<FilingHistory[]> {
  const res = await api.get(`/filing-history/${businessId}`)
  const raw = res.data
  const history = Array.isArray(raw) ? raw : (raw.history ?? [])
  return history.map(transformFilingHistory)
}

// ─── Exposure + regulation search ────────────────────────────────────────────

export interface ExposureSummary {
  total_pending: number
  total_exposure_inr: number
  by_urgency: Record<string, { count: number; max_penalty_total: number; avg_decay: number }>
}

export interface DecayTrendPoint {
  t: string  // ISO timestamp
  score: number
}

export type DecayTrends = Record<string, DecayTrendPoint[]>  // keyed by instance_id

export async function getDecayTrend(businessId: string): Promise<DecayTrends> {
  const res = await api.get(`/decay-trend/${businessId}`)
  return res.data?.trends ?? {}
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getBusiness(businessId: string): Promise<any> {
  const res = await api.get(`/business/${businessId}`)
  return res.data
}

export async function updateBusiness(
  businessId: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  updates: Record<string, any>,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Promise<any> {
  const res = await api.patch(`/business/${businessId}`, updates)
  return res.data
}

export async function getExposure(businessId: string): Promise<ExposureSummary> {
  const res = await api.get(`/exposure/${businessId}`)
  const raw = res.data
  return {
    total_pending: raw.total_pending ?? 0,
    total_exposure_inr: raw.total_exposure_inr ?? 0,
    by_urgency: raw.by_urgency ?? {},
  }
}

export interface RegulationSearchResult {
  _id: string
  name: string
  category: string
  frequency?: string
  deadline_rule?: string
  max_penalty_inr?: number
  source?: string
  state_specific?: string | null
  score?: number | null
}

export async function searchRegulations(
  q: string,
  category?: string,
): Promise<{ results: RegulationSearchResult[]; method: string; count: number }> {
  const res = await api.get('/search/regulations', {
    params: { q, ...(category ? { category } : {}) },
  })
  return res.data
}

// ─── Audit Replay (Tier A — novel: re-run past decisions against today's data) ─

export interface AgentDecisionRow {
  _id: string
  action: string
  timestamp: string
  payload: Record<string, unknown>
  has_trace: boolean
}

export interface ActionCount {
  action: string
  count: number
}

export interface DecisionsByActionResponse {
  business_id: string
  decisions: AgentDecisionRow[]
  action_counts: ActionCount[]
}

export interface DiffEntry {
  path: string
  kind: 'added' | 'removed' | 'changed'
  original: unknown
  current: unknown
}

export interface ReplayResponse {
  decision_id: string
  action: string
  original_timestamp: string | null
  original_payload: Record<string, unknown>
  replay_at: string
  replayable: boolean
  reason?: string
  current_output?: Record<string, unknown>
  diff?: DiffEntry[]
  original_record?: Record<string, unknown>
}

export async function getDecisionsByAction(businessId: string, action?: string): Promise<DecisionsByActionResponse> {
  const res = await api.get(`/agent-decisions/${businessId}/by-action`, {
    params: action ? { action } : {},
  })
  return res.data
}

export async function replayDecision(decisionId: string): Promise<ReplayResponse> {
  const res = await api.post(`/agent-decisions/replay/${decisionId}`)
  return res.data
}

// ─── Cross-business peer benchmark ──────────────────────────────────────────

export interface BenchmarkCohort {
  industry: string
  size_band: 'micro' | 'small' | 'medium' | 'large'
  size_band_range: { min: number; max: number }
  peer_count: number
  same_state_peer_count: number
}

export interface BenchmarkResponse {
  business_id: string
  cohort: BenchmarkCohort
  on_time: {
    your_rate: number | null
    your_filings: number
    cohort_avg_rate: number | null
    percentile: number | null
  }
  decay_health: {
    your_avg_decay: number | null
    cohort_avg_decay: number | null
    percentile: number | null
  }
}

export async function getBenchmark(businessId: string): Promise<BenchmarkResponse> {
  const res = await api.get(`/benchmark/${businessId}`)
  return res.data
}

// ─── Penalty Exposure Forecast (Time Series projection 30/60/90 days) ───────

export interface ForecastHorizon {
  days: number
  exposure_inr: number
  delta_inr: number
  newly_red_count: number
  obligations_overdue_count: number
}

export interface ForecastContributor {
  name: string
  amount_inr: number
  days_late_at_horizon: number
  due_date: string
}

export interface ExposureForecast {
  business_id: string
  horizons_days: number[]
  current_exposure_inr: number
  by_horizon: ForecastHorizon[]
  top_contributors: ForecastContributor[]
  total_pending: number
}

export async function getExposureForecast(businessId: string): Promise<ExposureForecast> {
  const res = await api.get(`/exposure-forecast/${businessId}`)
  return res.data
}

// ─── Compliance Health Score (single 0-100 number) ──────────────────────────

export interface HealthDimension {
  score: number
  weight: number
  detail: string
}

export interface HealthScore {
  business_id: string
  health_score: number
  band: 'excellent' | 'good' | 'fair' | 'poor' | 'critical'
  dimensions: {
    freshness: HealthDimension & { red: number; amber: number; green: number }
    on_time_rate: HealthDimension & { rate: number | null }
    ripple_exposure: HealthDimension & { recent: number; high: number }
    overdue_penalty: HealthDimension
  }
  computed_at: string
}

export async function getHealthScore(businessId: string): Promise<HealthScore> {
  const res = await api.get(`/health-score/${businessId}`)
  return res.data
}

// ─── Multi-tenant ripple cascade (Tier S #4) ─────────────────────────────────

export interface CascadeResult {
  business_id: string
  business_name: string
  industry: string
  state: string
  direct_count: number
  indirect_count: number
  severity: 'high' | 'medium' | 'low'
  detection_method: string
  top_direct: string[]
}

export interface CascadeResponse {
  title: string
  businesses_evaluated: number
  businesses_affected: number
  elapsed_ms: number
  hybrid: boolean
  results: CascadeResult[]
}

export async function rippleCascade(
  title: string,
  description: string,
  affectedCategories?: string[],
  hybrid: boolean = true,
): Promise<CascadeResponse> {
  const res = await api.post('/admin/ripple-cascade', {
    title,
    description,
    affected_categories: affectedCategories,
  }, { params: { hybrid, limit_businesses: 20 } })
  return res.data
}

// ─── Multimodal OCR upload (Tier S #3) ───────────────────────────────────────

export interface UploadCircularResponse {
  source: string
  ocr_extracted_chars: number
  ocr_preview: string
  ocr_mime_type: string
  ingestion: {
    reg_id: string
    name: string
    category: string
    businesses_affected: number
    ripple_summary: Array<{
      business_id: string
      business_name: string
      direct: number
      indirect: number
      severity: string
    }>
  }
}

export async function uploadCircular(
  file: File,
  source: string,
): Promise<UploadCircularResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('source', source)
  const res = await api.post('/admin/upload-circular', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return res.data
}

// ─── RAG explain-regulation (Tier S #5) ──────────────────────────────────────

export interface RegulationCitation {
  label: string  // "Reg-1"
  regulation_id: string
  name: string
  category: string
  found_by: string[]
  rrf_score: number | null
}

export interface RagAnswer {
  question: string
  answer: string
  citations: RegulationCitation[]
  retrieval_method: string
  retrieved_count: number
}

export async function explainRegulation(
  question: string,
  businessId?: string,
): Promise<RagAnswer> {
  const res = await api.post('/agent/explain-regulation', {
    question,
    business_id: businessId,
  }, { timeout: 60000 })
  return res.data
}

// ─── Real-time events (Tier S #1 — Change Streams via SSE) ───────────────────

export interface ChangeStreamEvent {
  at?: string
  kind?: string
  collection?: string
  operation?: string
  business_id?: string | null
  title?: string
  category?: string
  severity?: string
  direct_count?: number
  indirect_count?: number
  action?: string
  preview?: string
  name?: string
  urgency?: string
  decay_score?: number
  changed_fields?: string[]
}

/**
 * Subscribe to MongoDB Change Stream events for a business via SSE.
 * Returns a cleanup function to close the connection.
 */
export function subscribeToEvents(
  businessId: string | null,
  onEvent: (event: ChangeStreamEvent) => void,
): () => void {
  const params = new URLSearchParams()
  if (businessId) params.set('business_id', businessId)
  const url = `${BASE_URL}/events/stream${params.toString() ? '?' + params : ''}`
  const es = new EventSource(url)
  es.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as ChangeStreamEvent)
    } catch {
      // ignore malformed event
    }
  }
  es.onerror = () => {
    // EventSource auto-reconnects; nothing to do
  }
  return () => es.close()
}

// ─── Agent (multi-agent Compliance Officer) ───────────────────────────────────

export interface AgentEventPart {
  text?: string
  tool?: string
  args?: Record<string, unknown>
  tool_result?: string
  response?: Record<string, unknown>
}

export interface AgentEvent {
  kind?: string
  author?: string
  at?: string
  parts?: AgentEventPart[]
  content?: string
  answer?: string
  step_count?: number
  message?: string
}

/**
 * Stream the agent's reasoning events via Server-Sent Events.
 * The callback fires for each event; the returned promise resolves when
 * the stream closes.
 *
 * We use fetch + ReadableStream rather than EventSource because EventSource
 * only supports GET, and our endpoint is POST (carries the question body).
 */
export async function streamAgent(
  question: string,
  businessId: string | undefined,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = `${BASE_URL}/agent/stream`
  // Axios interceptors don't run on raw fetch(), so attach the token here.
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const user = auth.currentUser
  if (user) {
    try {
      const token = await user.getIdToken()
      headers.Authorization = `Bearer ${token}`
    } catch {
      // proceed unauthenticated
    }
  }

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ question, business_id: businessId }),
    signal,
  })

  if (!res.body) {
    throw new Error('Agent stream returned no body')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE messages are separated by \n\n
    const messages = buffer.split('\n\n')
    buffer = messages.pop() ?? ''  // last chunk may be incomplete

    for (const msg of messages) {
      const dataLine = msg.split('\n').find((l) => l.startsWith('data:'))
      if (!dataLine) continue
      const payload = dataLine.slice(5).trim()
      if (!payload) continue
      try {
        onEvent(JSON.parse(payload) as AgentEvent)
      } catch {
        // ignore malformed chunk
      }
    }
  }
}

/**
 * Blocking variant — returns the final answer and the full trace at once.
 * Use this when streaming isn't worth the complexity.
 */
export async function askAgent(
  question: string,
  businessId?: string,
): Promise<{ answer: string; trace: AgentEvent[]; step_count: number }> {
  const res = await api.post('/agent/ask', { question, business_id: businessId })
  return res.data
}
