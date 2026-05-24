import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

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
  if (score < 20) return { border: 'border-red-500', text: 'text-red-600', bg: 'bg-red-50', badge: 'bg-red-100 text-red-700' }
  if (score <= 40) return { border: 'border-amber-500', text: 'text-amber-600', bg: 'bg-amber-50', badge: 'bg-amber-100 text-amber-700' }
  return { border: 'border-green-500', text: 'text-green-600', bg: 'bg-green-50', badge: 'bg-green-100 text-green-700' }
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
